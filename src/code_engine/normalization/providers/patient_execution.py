"""Patient, resumable execution state for L2 external entity providers."""

from __future__ import annotations

import hashlib
import json
import os
import queue
import random
import signal
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from code_engine.normalization.candidates import EntityResolutionRequest


RESOLVER_SEMANTIC_VERSION = "entity_provider_semantics_v1"


class ProviderRetryableError(RuntimeError):
    def __init__(self, category: str, message: str = ""):
        super().__init__(message or category)
        self.category = category


class ProviderNegativeTerminal(RuntimeError):
    def __init__(self, category: str, message: str = ""):
        super().__init__(message or category)
        self.category = category


@dataclass(frozen=True)
class ProviderExecutionConfig:
    connect_timeout_seconds: float = 60.0
    read_timeout_seconds: float = 600.0
    attempt_watchdog_seconds: float = 900.0
    current_run_retry_delays_seconds: tuple[float, ...] = (10.0, 30.0, 90.0, 300.0)
    heartbeat_interval_seconds: float = 30.0
    provider_cooldown_seconds: float = 300.0
    circuit_failure_threshold: int = 5

    @classmethod
    def from_env(cls) -> "ProviderExecutionConfig":
        def num(name: str, default: float) -> float:
            raw = os.environ.get(name)
            if raw in (None, ""):
                return default
            try:
                return float(raw)
            except ValueError:
                return default

        return cls(
            connect_timeout_seconds=num("CODE_L2_PROVIDER_CONNECT_TIMEOUT_SECONDS", 60.0),
            read_timeout_seconds=num("CODE_L2_PROVIDER_READ_TIMEOUT_SECONDS", 600.0),
            attempt_watchdog_seconds=num("CODE_L2_PROVIDER_ATTEMPT_WATCHDOG_SECONDS", 900.0),
            heartbeat_interval_seconds=num("CODE_L2_PROVIDER_HEARTBEAT_SECONDS", 30.0),
            provider_cooldown_seconds=num("CODE_L2_PROVIDER_COOLDOWN_SECONDS", 300.0),
            circuit_failure_threshold=int(num("CODE_L2_PROVIDER_CIRCUIT_FAILURE_THRESHOLD", 5.0)),
        )


@dataclass
class ProviderQueryState:
    query_key: str
    query_hash: str
    provider: str
    normalized_mention: str
    expected_entity_type: str
    species_context: str
    granularity: str
    provider_query_mode: str
    semantic_resolver_version: str = RESOLVER_SEMANTIC_VERSION
    status: str = "pending"
    attempt_count_total: int = 0
    attempt_count_current_run: int = 0
    last_error_category: str | None = None
    last_error_message_safe: str | None = None
    last_attempt_at: str | None = None
    next_retry_at: str | None = None
    result_cache_ref: str | None = None
    created_run_id: str = ""
    last_run_id: str = ""
    consumers: list[dict[str, str]] = field(default_factory=list)
    last_completed_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "query_key": self.query_key,
            "query_hash": self.query_hash,
            "provider": self.provider,
            "normalized_mention": self.normalized_mention,
            "expected_entity_type": self.expected_entity_type,
            "species_context": self.species_context,
            "granularity": self.granularity,
            "provider_query_mode": self.provider_query_mode,
            "semantic_resolver_version": self.semantic_resolver_version,
            "status": self.status,
            "attempt_count_total": self.attempt_count_total,
            "attempt_count_current_run": self.attempt_count_current_run,
            "last_error_category": self.last_error_category,
            "last_error_message_safe": self.last_error_message_safe,
            "last_attempt_at": self.last_attempt_at,
            "next_retry_at": self.next_retry_at,
            "result_cache_ref": self.result_cache_ref,
            "created_run_id": self.created_run_id,
            "last_run_id": self.last_run_id,
            "consumers": self.consumers,
            "last_completed_at": self.last_completed_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProviderQueryState":
        fields = cls.__dataclass_fields__
        return cls(**{name: payload.get(name) for name in fields if name in payload})


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_error_message(exc: BaseException) -> str:
    return " ".join(str(exc).split())[:240]


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def stable_query_identity(provider_name: str, request: EntityResolutionRequest, provider_cache_key: Any, mode: str = "direct") -> tuple[str, str]:
    payload = {
        "provider": provider_name,
        "normalized_mention": " ".join(str(request.surface or "").casefold().split()),
        "expected_entity_type": str(request.l1_entity_type_hint or ""),
        "species_context": str(request.species_context or ""),
        "granularity": str(request.mention_granularity or ""),
        "provider_query_mode": mode,
        "semantic_resolver_version": RESOLVER_SEMANTIC_VERSION,
        "provider_cache_key": provider_cache_key,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return encoded, digest


def classify_provider_exception(exc: BaseException) -> str:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timeout" in name or "timed out" in message:
        return "read_timeout"
    if "connect" in name or "connection" in name:
        return "connection_error"
    if "dns" in message or "name resolution" in message or "gaierror" in name:
        return "dns_error"
    if "ssl" in name or "tls" in message or "certificate" in message:
        return "tls_error"
    if "429" in message:
        return "http_429"
    for code in ("500", "502", "503", "504"):
        if code in message:
            return f"http_{code}"
    return "provider_exception"


class L2ProviderExecutionManager:
    """Persistent ledger/cache for patient L2 provider lookups."""

    def __init__(self, run_dir: str | Path, *, config: ProviderExecutionConfig | None = None, run_id: str | None = None, time_fn: Callable[[], float] | None = None, sleep_fn: Callable[[float], None] | None = None):
        self.run_dir = Path(run_dir)
        self.run_id = run_id or self.run_dir.name
        self.config = config or ProviderExecutionConfig.from_env()
        self.time_fn = time_fn or time.time
        self.sleep_fn = sleep_fn or time.sleep
        self.artifacts = self.run_dir / "artifacts"
        self.ledger_path = self.artifacts / "l2_provider_query_ledger.json"
        self.summary_path = self.artifacts / "l2_provider_query_ledger_summary.json"
        self.heartbeat_path = self.artifacts / "l2_provider_heartbeat.json"
        self.cache_dir = self.artifacts / "l2_provider_result_cache"
        self.lock = threading.RLock()
        self.states: dict[str, ProviderQueryState] = {}
        self.cooldowns: dict[str, dict[str, Any]] = {}
        self.consecutive_failures: dict[str, int] = {}
        self.stop_requested = False
        self.active: dict[str, Any] | None = None
        self.metrics = {
            "raw_provider_query_requests": 0,
            "unique_provider_query_keys": 0,
            "deduplicated_requests": 0,
            "persistent_cache_hits": 0,
            "negative_cache_hits": 0,
            "network_attempts": 0,
            "retryable_failures": 0,
            "resumed_queries": 0,
        }
        self._load()
        self._repair_running_from_previous_run()
        self._install_signal_handlers()
        self._write_all()

    def _install_signal_handlers(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            return
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                previous = signal.getsignal(sig)
                if previous not in (signal.SIG_DFL, signal.SIG_IGN):
                    continue

                def handler(signum, _frame, self=self):
                    self.request_stop(f"signal_{signum}")
                    raise KeyboardInterrupt(f"interrupted_by_signal_{signum}")

                signal.signal(sig, handler)
            except Exception:
                continue

    def request_stop(self, reason: str = "interrupted") -> None:
        with self.lock:
            self.stop_requested = True
            for state in self.states.values():
                if state.status == "running":
                    state.status = "retryable_failed"
                    state.last_error_category = reason
                    state.last_error_message_safe = reason
                    state.next_retry_at = now_iso()
            self._write_all_locked()

    def _load(self) -> None:
        if not self.ledger_path.exists():
            self._bootstrap_from_legacy_decisions()
            return
        try:
            payload = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except Exception:
            return
        for item in payload.get("queries", []):
            state = ProviderQueryState.from_dict(item)
            self.states[state.query_hash] = state
        self.cooldowns = dict(payload.get("provider_cooldowns") or {})
        self.metrics.update(payload.get("metrics") or {})

    def _bootstrap_from_legacy_decisions(self) -> None:
        decisions_path = self.artifacts / "entity_resolution_decisions.jsonl"
        if not decisions_path.exists():
            return
        external_names = {
            "PubChemCandidateProvider",
            "ChEMBLCandidateProvider",
            "MyGeneCandidateProvider",
            "UniProtCandidateProvider",
            "OLSOntologyCandidateProvider",
        }
        try:
            lines = decisions_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return
        for line in lines:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                request = EntityResolutionRequest.model_validate(item.get("request") or {})
            except Exception:
                continue
            candidates = list(item.get("candidates") or [])
            for trace in item.get("provider_trace", []):
                provider = str(trace.get("provider_name") or "")
                status = str(trace.get("status") or "")
                if provider not in external_names or status in {"not_applicable", "not_needed", "error", "retryable_failed"}:
                    continue
                provider_key = self._legacy_provider_cache_key(provider, request)
                state = self.state_for(provider, request, provider_key)
                if state.status in {"completed", "negative_terminal"}:
                    continue
                provider_candidates = [self._candidate_as_record(c) for c in candidates if c.get("provider_name") == provider]
                if status == "candidates_returned" and provider_candidates:
                    self._write_cache_then_complete(state, provider_candidates)
                    state.status = "completed"
                    state.last_completed_at = now_iso()
                elif status == "no_candidates":
                    self._write_cache_then_complete(state, [])
                    state.status = "negative_terminal"
                    state.last_completed_at = now_iso()
        if self.states:
            self.metrics["unique_provider_query_keys"] = len(self.states)

    @staticmethod
    def _legacy_provider_cache_key(provider: str, request: EntityResolutionRequest) -> Any:
        if provider == "OLSOntologyCandidateProvider":
            try:
                from code_engine.normalization.providers.ontology import OLS_ONTOLOGIES, TYPE_ONTOLOGY_ROUTES
                etype = request.l1_entity_type_hint or "unknown"
                routes = list(TYPE_ONTOLOGY_ROUTES.get(etype, []))
                if etype == "phenotype":
                    context = f"{request.context_text or ''} {request.surface}".casefold()
                    clinical = any(term in context for term in ("patient", "clinical", "human", "syndrome", "disease"))
                    routes = ["hp", "mondo"] if clinical else ["efo", "ncit", "go", "mondo"]
                if etype == "pathway":
                    routes = ["go"]
                return (request.surface.casefold().strip(), str(request.l1_entity_type_hint or ""), tuple(item for item in routes if item in OLS_ONTOLOGIES))
            except Exception:
                pass
        return (
            request.surface.casefold().strip(),
            str(request.l1_entity_type_hint or ""),
            tuple(request.allowed_entity_types),
            str(request.species_context or ""),
            str(request.mention_granularity or ""),
        )

    @staticmethod
    def _candidate_as_record(candidate: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider_record_id": candidate.get("provider_record_id") or candidate.get("canonical_id"),
            "canonical_id": candidate.get("canonical_id"),
            "canonical_name": candidate.get("canonical_name"),
            "name": candidate.get("canonical_name"),
            "normalized_surface": candidate.get("normalized_surface"),
            "entity_type": candidate.get("entity_type"),
            "semantic_level": candidate.get("semantic_level"),
            "external_ids": candidate.get("external_ids") or {},
            "aliases": candidate.get("aliases") or [],
            "match_type": candidate.get("match_type"),
            "match_score": candidate.get("match_score", candidate.get("overall_score", 0.0)),
            "type_score": candidate.get("type_score", 0.0),
            "source_reliability": candidate.get("source_reliability", 0.0),
            "context_score": candidate.get("context_score", 0.0),
            "score": candidate.get("overall_score", candidate.get("match_score", 0.0)),
            "supporting_context": candidate.get("supporting_context") or {},
            "warnings": candidate.get("warnings") or [],
        }

    def _repair_running_from_previous_run(self) -> None:
        for state in self.states.values():
            if state.status == "running" and state.last_run_id != self.run_id:
                state.status = "retryable_failed"
                state.last_error_category = "interrupted"
                state.last_error_message_safe = "previous run ended while query was running"
                state.next_retry_at = now_iso()
                self.metrics["resumed_queries"] += 1
                state.attempt_count_current_run = 0

    def _write_all(self) -> None:
        with self.lock:
            self._write_all_locked()

    def _write_all_locked(self) -> None:
        self.metrics["unique_provider_query_keys"] = len(self.states)
        payload = {
            "schema_version": "l2_provider_query_ledger.v1",
            "run_id": self.run_id,
            "config": self.config.__dict__,
            "metrics": self.metrics,
            "provider_cooldowns": self.cooldowns,
            "queries": [state.as_dict() for state in sorted(self.states.values(), key=lambda s: s.query_hash)],
        }
        atomic_write_json(self.ledger_path, payload)
        atomic_write_json(self.summary_path, self.summary())

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        by_provider: dict[str, dict[str, int]] = {}
        for state in self.states.values():
            counts[state.status] = counts.get(state.status, 0) + 1
            provider_counts = by_provider.setdefault(state.provider, {})
            provider_counts[state.status] = provider_counts.get(state.status, 0) + 1
        return {
            "schema_version": "l2_provider_query_ledger_summary.v1",
            "run_id": self.run_id,
            **self.metrics,
            "status_counts": counts,
            "status_counts_by_provider": by_provider,
            "network_attempts_by_provider": self._network_attempts_by_provider(),
            "provider_cooldowns": self.cooldowns,
        }

    def _network_attempts_by_provider(self) -> dict[str, int]:
        values: dict[str, int] = {}
        for state in self.states.values():
            values[state.provider] = values.get(state.provider, 0) + state.attempt_count_total
        return values

    def state_for(self, provider_name: str, request: EntityResolutionRequest, provider_cache_key: Any, *, mode: str = "direct") -> ProviderQueryState:
        query_key, query_hash = stable_query_identity(provider_name, request, provider_cache_key, mode)
        with self.lock:
            state = self.states.get(query_hash)
            if state is None:
                state = ProviderQueryState(
                    query_key=query_key,
                    query_hash=query_hash,
                    provider=provider_name,
                    normalized_mention=" ".join(str(request.surface or "").casefold().split()),
                    expected_entity_type=str(request.l1_entity_type_hint or ""),
                    species_context=str(request.species_context or ""),
                    granularity=str(request.mention_granularity or ""),
                    provider_query_mode=mode,
                    status="pending",
                    created_run_id=self.run_id,
                    last_run_id=self.run_id,
                )
                self.states[query_hash] = state
            state.last_run_id = self.run_id
            consumer = {
                "paper_id": str(request.paper_id or ""),
                "claim_id": str(request.claim_id or ""),
                "observation_id": str(request.observation_id or ""),
                "endpoint_role": str(request.endpoint_role or ""),
            }
            if consumer not in state.consumers:
                state.consumers.append(consumer)
            return state

    def execute(self, provider_name: str, request: EntityResolutionRequest, provider_cache_key: Any, search_fn: Callable[[], list[dict[str, Any]]], *, mode: str = "direct") -> tuple[str, list[dict[str, Any]], list[str]]:
        state = self.state_for(provider_name, request, provider_cache_key, mode=mode)
        self.metrics["raw_provider_query_requests"] += 1
        if state.status == "completed" and state.result_cache_ref:
            records = self._read_cache(state)
            self.metrics["persistent_cache_hits"] += 1
            self.metrics["deduplicated_requests"] += 1
            self._write_all()
            return "completed_cache_hit", records, ["provider_persistent_cache_hit"]
        if state.status == "negative_terminal":
            self.metrics["negative_cache_hits"] += 1
            self.metrics["deduplicated_requests"] += 1
            self._write_all()
            return "negative_cache_hit", [], ["provider_negative_cache_hit"]
        if state.status in {"running", "retryable_failed"} and not self._retry_due(state):
            self.metrics["deduplicated_requests"] += 1
            self._write_all()
            return "retry_pending", [], ["provider_resolution_pending"]
        if self.stop_requested:
            state.status = "retryable_failed"
            state.last_error_category = "interrupted"
            state.next_retry_at = now_iso()
            self._write_all()
            return "retryable_failed", [], ["provider_resolution_pending"]

        retry_delays = (0.0,) + self.config.current_run_retry_delays_seconds
        last_category = "provider_exception"
        for attempt_index, delay in enumerate(retry_delays):
            if attempt_index > 0:
                self._sleep_backoff(provider_name, delay)
            if self.stop_requested:
                state.status = "retryable_failed"
                state.last_error_category = "interrupted"
                state.next_retry_at = now_iso()
                self._write_all()
                return "retryable_failed", [], ["provider_resolution_pending"]
            self._wait_for_cooldown(provider_name)
            try:
                records = self._attempt(provider_name, state, search_fn)
                self._write_cache_then_complete(state, records)
                self.consecutive_failures[provider_name] = 0
                status = "completed" if records else "negative_terminal"
                state.status = status
                state.last_error_category = None
                state.last_error_message_safe = None
                state.next_retry_at = None
                state.last_completed_at = now_iso()
                self._write_all()
                return ("completed" if records else "negative_terminal"), records, []
            except ProviderNegativeTerminal as exc:
                state.status = "negative_terminal"
                state.last_error_category = exc.category
                state.last_error_message_safe = safe_error_message(exc)
                state.next_retry_at = None
                state.last_completed_at = now_iso()
                self._write_cache_then_complete(state, [])
                self._write_all()
                return "negative_terminal", [], []
            except BaseException as exc:
                last_category = getattr(exc, "category", classify_provider_exception(exc))
                state.status = "retryable_failed"
                state.last_error_category = last_category
                state.last_error_message_safe = safe_error_message(exc)
                next_delay = delay if delay > 0 else (self.config.current_run_retry_delays_seconds[0] if self.config.current_run_retry_delays_seconds else 0.0)
                state.next_retry_at = self._next_retry_iso(next_delay)
                self.metrics["retryable_failures"] += 1
                self._record_provider_failure(provider_name, last_category)
                self._write_all()
        return "retryable_failed", [], [f"provider_resolution_pending:{last_category}"]

    def _retry_due(self, state: ProviderQueryState) -> bool:
        if not state.next_retry_at:
            return True
        try:
            target = datetime.fromisoformat(state.next_retry_at).timestamp()
        except ValueError:
            return True
        return self.time_fn() >= target

    def _next_retry_iso(self, delay: float) -> str:
        return datetime.fromtimestamp(self.time_fn() + max(0.0, delay), tz=timezone.utc).isoformat()

    def _sleep_backoff(self, provider_name: str, delay: float) -> None:
        jitter = min(delay * 0.2, 5.0) * random.random()
        target = self.time_fn() + delay + jitter
        while self.time_fn() < target:
            if self.stop_requested:
                return
            self.write_heartbeat(active_provider=provider_name)
            self.sleep_fn(min(1.0, target - self.time_fn()))

    def _wait_for_cooldown(self, provider_name: str) -> None:
        info = self.cooldowns.get(provider_name)
        if not info:
            return
        try:
            until = datetime.fromisoformat(str(info.get("cooldown_until"))).timestamp()
        except ValueError:
            return
        while self.time_fn() < until and not self.stop_requested:
            info["probe_attempt"] = True
            self.write_heartbeat(active_provider=provider_name)
            self.sleep_fn(min(5.0, until - self.time_fn()))

    def _record_provider_failure(self, provider_name: str, category: str) -> None:
        retryable = {"connection_timeout", "read_timeout", "connection_error", "dns_error", "tls_error", "http_429", "http_500", "http_502", "http_503", "http_504", "provider_unavailable", "attempt_watchdog_timeout"}
        if category not in retryable:
            return
        count = self.consecutive_failures.get(provider_name, 0) + 1
        self.consecutive_failures[provider_name] = count
        if count >= self.config.circuit_failure_threshold:
            self.cooldowns[provider_name] = {
                "circuit_opened_at": now_iso(),
                "cooldown_until": self._next_retry_iso(self.config.provider_cooldown_seconds),
                "probe_attempt": False,
                "last_error_category": category,
            }

    def _attempt(self, provider_name: str, state: ProviderQueryState, search_fn: Callable[[], list[dict[str, Any]]]) -> list[dict[str, Any]]:
        state.status = "running"
        state.attempt_count_total += 1
        state.attempt_count_current_run += 1
        state.last_attempt_at = now_iso()
        self.metrics["network_attempts"] += 1
        self.active = {"provider": provider_name, "query_hash": state.query_hash, "query_safe": state.normalized_mention, "started_at": self.time_fn()}
        self.write_heartbeat(active_provider=provider_name, active_query_safe=state.normalized_mention)
        self._write_all()
        try:
            result_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

            def target() -> None:
                try:
                    result_queue.put(("ok", search_fn()), block=False)
                except BaseException as exc:
                    result_queue.put(("error", exc), block=False)

            worker = threading.Thread(target=target, name=f"l2_provider_{provider_name}_{state.query_hash[:8]}", daemon=True)
            worker.start()
            try:
                kind, value = result_queue.get(timeout=self.config.attempt_watchdog_seconds)
            except queue.Empty as exc:
                raise ProviderRetryableError("attempt_watchdog_timeout", f"{provider_name} attempt watchdog expired") from exc
            if kind == "error":
                raise value
            return value
        finally:
            self.active = None
            self.write_heartbeat()

    def _cache_path(self, state: ProviderQueryState) -> Path:
        return self.cache_dir / state.provider / f"{state.query_hash}.json"

    def _write_cache_then_complete(self, state: ProviderQueryState, records: list[dict[str, Any]]) -> None:
        path = self._cache_path(state)
        atomic_write_json(path, {"query_hash": state.query_hash, "provider": state.provider, "records": records, "written_at": now_iso()})
        state.result_cache_ref = str(path.relative_to(self.run_dir))

    def _read_cache(self, state: ProviderQueryState) -> list[dict[str, Any]]:
        if not state.result_cache_ref:
            return []
        path = self.run_dir / state.result_cache_ref
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            state.status = "retryable_failed"
            state.last_error_category = "cache_missing"
            state.next_retry_at = now_iso()
            return []
        return list(payload.get("records") or [])

    def write_heartbeat(self, *, active_provider: str | None = None, active_query_safe: str | None = None) -> None:
        with self.lock:
            active = self.active or {}
            started = active.get("started_at")
            heartbeat = {
                "schema_version": "l2_provider_heartbeat.v1",
                "stage": "l2_entity_resolution",
                "active_provider": active_provider or active.get("provider"),
                "active_query_safe": active_query_safe or active.get("query_safe"),
                "active_attempt_elapsed_seconds": int(max(0.0, self.time_fn() - started)) if started else 0,
                "completed_queries": sum(1 for s in self.states.values() if s.status == "completed"),
                "pending_queries": sum(1 for s in self.states.values() if s.status == "pending"),
                "retryable_queries": sum(1 for s in self.states.values() if s.status == "retryable_failed"),
                "negative_terminal_queries": sum(1 for s in self.states.values() if s.status == "negative_terminal"),
                "next_provider_retry_at": min((str(v.get("cooldown_until")) for v in self.cooldowns.values() if v.get("cooldown_until")), default=None),
                "last_success_at": max((s.last_completed_at for s in self.states.values() if s.last_completed_at), default=None),
                "process_heartbeat_at": now_iso(),
                "stop_requested": self.stop_requested,
            }
            atomic_write_json(self.heartbeat_path, heartbeat)
