import json
import time
from pathlib import Path

import pytest

from code_engine.normalization.candidates import EntityResolutionRequest
from code_engine.normalization.providers.base import ExternalCandidateProvider
from code_engine.normalization.providers.patient_execution import (
    L2ProviderExecutionManager,
    ProviderExecutionConfig,
    ProviderRetryableError,
)


class FakeClock:
    def __init__(self):
        self.value = 1_700_000_000.0

    def time(self):
        return self.value

    def sleep(self, seconds):
        self.value += max(0.0, seconds)


class FakeClient:
    network_call_cost = 1

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def search(self, surface, request=None):
        self.calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else [{"provider_record_id": "X", "canonical_id": "DB:X", "canonical_name": surface, "entity_type": "gene"}]
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            return outcome()
        return outcome


class FakeProvider(ExternalCandidateProvider):
    name = "FakeProvider"
    resource_name = "FakeDB"
    supported_entity_types = ["gene", "protein"]


def cfg(**kwargs):
    values = {
        "connect_timeout_seconds": 60,
        "read_timeout_seconds": 600,
        "attempt_watchdog_seconds": 0.2,
        "current_run_retry_delays_seconds": (),
        "heartbeat_interval_seconds": 0.01,
        "provider_cooldown_seconds": 5,
        "circuit_failure_threshold": 2,
    }
    values.update(kwargs)
    return ProviderExecutionConfig(**values)


def request(surface="E-cadherin", species="human", etype="gene"):
    return EntityResolutionRequest(
        surface=surface,
        l1_entity_type_hint=etype,
        species_context=species,
        mention_granularity=etype,
        execute=True,
        network_enabled=True,
    )


def manager(tmp_path: Path, clock=None, **kwargs):
    clock = clock or FakeClock()
    return L2ProviderExecutionManager(tmp_path, config=cfg(**kwargs), time_fn=clock.time, sleep_fn=clock.sleep)


def read_summary(run_dir: Path):
    return json.loads((run_dir / "artifacts/l2_provider_query_ledger_summary.json").read_text())


def test_slow_request_inside_watchdog_completes(tmp_path):
    client = FakeClient([[{"provider_record_id": "1", "canonical_id": "DB:1", "canonical_name": "E-cadherin", "entity_type": "gene"}]])
    provider = FakeProvider(client, execution_manager=manager(tmp_path, attempt_watchdog_seconds=1.0))

    candidates = provider.propose(request())

    assert client.calls == 1
    assert len(candidates) == 1
    assert read_summary(tmp_path)["status_counts"]["completed"] == 1


def test_dead_socket_attempt_becomes_retryable_not_negative(tmp_path):
    def stuck():
        time.sleep(0.5)
        return []

    client = FakeClient([stuck])
    provider = FakeProvider(client, execution_manager=manager(tmp_path, attempt_watchdog_seconds=0.05))

    candidates = provider.propose(request())

    assert candidates == []
    assert provider.last_status == "retryable_failed"
    summary = read_summary(tmp_path)
    assert summary["status_counts"]["retryable_failed"] == 1
    assert "negative_terminal" not in summary["status_counts"]


def test_resume_retryable_query_then_completes(tmp_path):
    client = FakeClient([ProviderRetryableError("http_503", "temporary")])
    provider = FakeProvider(client, execution_manager=manager(tmp_path))

    assert provider.propose(request()) == []
    assert read_summary(tmp_path)["status_counts"]["retryable_failed"] == 1

    clock = FakeClock()
    clock.value += 999
    resumed = L2ProviderExecutionManager(tmp_path, config=cfg(), time_fn=clock.time, sleep_fn=clock.sleep)
    provider = FakeProvider(FakeClient([[{"provider_record_id": "2", "canonical_id": "DB:2", "canonical_name": "E-cadherin", "entity_type": "gene"}]]), execution_manager=resumed)

    assert len(provider.propose(request())) == 1
    assert read_summary(tmp_path)["status_counts"]["completed"] == 1


def test_completed_query_does_not_repeat_network(tmp_path):
    client = FakeClient([[{"provider_record_id": "1", "canonical_id": "DB:1", "canonical_name": "E-cadherin", "entity_type": "gene"}]])
    provider = FakeProvider(client, execution_manager=manager(tmp_path))

    assert len(provider.propose(request())) == 1
    assert len(provider.propose(request())) == 1

    summary = read_summary(tmp_path)
    assert client.calls == 1
    assert summary["persistent_cache_hits"] == 1
    assert summary["deduplicated_requests"] == 1


def test_same_query_multiple_consumers_one_network_call(tmp_path):
    mgr = manager(tmp_path)
    client = FakeClient([[{"provider_record_id": "1", "canonical_id": "DB:1", "canonical_name": "E-cadherin", "entity_type": "gene"}]])
    provider = FakeProvider(client, execution_manager=mgr)

    first = request()
    first.claim_id = "claim-a"
    second = request()
    second.claim_id = "claim-b"
    provider.propose(first)
    provider.propose(second)

    ledger = json.loads((tmp_path / "artifacts/l2_provider_query_ledger.json").read_text())
    assert client.calls == 1
    assert len(ledger["queries"]) == 1
    assert len(ledger["queries"][0]["consumers"]) == 2


def test_different_species_do_not_merge(tmp_path):
    client = FakeClient([
        [{"provider_record_id": "H", "canonical_id": "DB:H", "canonical_name": "human", "entity_type": "gene"}],
        [{"provider_record_id": "M", "canonical_id": "DB:M", "canonical_name": "mouse", "entity_type": "gene"}],
    ])
    provider = FakeProvider(client, execution_manager=manager(tmp_path))

    provider.propose(request(species="human"))
    provider.propose(request(species="mouse"))

    assert client.calls == 2
    assert read_summary(tmp_path)["unique_provider_query_keys"] == 2


def test_429_uses_backoff_then_recovers(tmp_path):
    clock = FakeClock()
    client = FakeClient([
        ProviderRetryableError("http_429", "rate limited"),
        [{"provider_record_id": "1", "canonical_id": "DB:1", "canonical_name": "E-cadherin", "entity_type": "gene"}],
    ])
    provider = FakeProvider(client, execution_manager=manager(tmp_path, clock, current_run_retry_delays_seconds=(10.0,)))

    assert len(provider.propose(request())) == 1
    summary = read_summary(tmp_path)
    assert client.calls == 2
    assert summary["retryable_failures"] == 1
    assert summary["status_counts"]["completed"] == 1


def test_circuit_cooldown_reopens_for_later_probe(tmp_path):
    clock = FakeClock()
    client = FakeClient([
        ProviderRetryableError("http_503", "down"),
        ProviderRetryableError("http_503", "down"),
    ])
    provider = FakeProvider(client, execution_manager=manager(tmp_path, clock, circuit_failure_threshold=1, current_run_retry_delays_seconds=(1.0,)))

    provider.propose(request())

    summary = read_summary(tmp_path)
    assert "FakeProvider" in summary["provider_cooldowns"]
    assert summary["status_counts"]["retryable_failed"] == 1


def test_empty_result_enters_negative_cache(tmp_path):
    provider = FakeProvider(FakeClient([[]]), execution_manager=manager(tmp_path))

    assert provider.propose(request()) == []
    assert provider.last_status == "no_candidates"
    assert read_summary(tmp_path)["status_counts"]["negative_terminal"] == 1


def test_running_from_dead_run_is_recoverable(tmp_path):
    mgr = manager(tmp_path)
    state = mgr.state_for("FakeProvider", request(), ("e-cadherin", "gene", (), "human", "gene"))
    state.status = "running"
    state.last_run_id = "old-run"
    mgr._write_all()

    resumed = L2ProviderExecutionManager(tmp_path, config=cfg())

    assert read_summary(tmp_path)["status_counts"]["retryable_failed"] == 1
    assert resumed.metrics["resumed_queries"] == 1


def test_checkpoint_keeps_completed_result_after_interruption(tmp_path):
    mgr = manager(tmp_path)
    provider = FakeProvider(FakeClient([[{"provider_record_id": "1", "canonical_id": "DB:1", "canonical_name": "E-cadherin", "entity_type": "gene"}]]), execution_manager=mgr)
    provider.propose(request())
    mgr.request_stop("test_sigterm")

    resumed = L2ProviderExecutionManager(tmp_path, config=cfg())
    provider = FakeProvider(FakeClient([]), execution_manager=resumed)

    assert len(provider.propose(request())) == 1
    assert read_summary(tmp_path)["persistent_cache_hits"] == 1


def test_heartbeat_updates_without_ending_run(tmp_path):
    mgr = manager(tmp_path)
    mgr.write_heartbeat(active_provider="FakeProvider", active_query_safe="E-cadherin")

    heartbeat = json.loads((tmp_path / "artifacts/l2_provider_heartbeat.json").read_text())
    assert heartbeat["stage"] == "l2_entity_resolution"
    assert heartbeat["active_provider"] == "FakeProvider"
    assert heartbeat["stop_requested"] is False

