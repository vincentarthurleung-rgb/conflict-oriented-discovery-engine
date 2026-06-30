"""Local JSON-backed knowledge-store adapter for existing pipeline artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from code_engine.common.runtime import ensure_source_allowed, is_legacy_source


DEFAULT_STORE_PATH = Path("data/index/knowledge_store.json")
PAIR_SEPARATOR = "\u241f"


def empty_knowledge_store(status: str = "missing_empty_store") -> Dict[str, Any]:
    """Return a query-safe empty store without creating runtime files."""

    return {
        "schema_version": "query_knowledge_store_v1",
        "generated_at": None,
        "knowledge_store_status": status,
        "runtime_data_status": "no_graph_runtime_data",
        "using_legacy_data": False,
        "entities": [],
        "triples": [],
        "pairs": {},
        "conflict_edges": [],
        "context_mentions": [],
        "validation_results": [],
        "hypotheses": [],
        "hypothesis_pairs": {},
        "warnings": ["Knowledge store is unavailable; an empty store was used."],
    }


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _as_list(payload: Any, keys: Iterable[str] = ()) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in keys:
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
    return []


def _normalized_value(record: Dict[str, Any], role: str) -> Tuple[str, bool]:
    """Prefer v2 fields and report whether a compatibility fallback was needed."""

    preferred = (f"normalized_{role}_v2", f"normalized_{role}")
    fallback = (f"canonical_{role}", "source" if role == "subject" else "target", role)
    for key in preferred:
        if record.get(key):
            return str(record[key]).upper().strip(), False
    for key in fallback:
        if record.get(key):
            return str(record[key]).upper().strip(), True
    return "", True


def _pair_key(subject: str, obj: str) -> str:
    return f"{str(subject).upper().strip()}{PAIR_SEPARATOR}{str(obj).upper().strip()}"


def _load_hypotheses(root: Path) -> List[Dict[str, Any]]:
    for relative in (
        "data/processed/l5/validated_hypotheses.json",
        "data/processed/l4/hypothesis_search_results.json",
    ):
        payload = _read_json(root / relative)
        records = _as_list(payload, ("hypotheses", "validated_hypotheses", "ranked_hypotheses"))
        if records:
            return records
    return []


def build_knowledge_store(
    repository_root: str | Path = ".",
    *,
    output_path: str | Path | None = None,
    allow_legacy_source: bool = False,
) -> Dict[str, Any]:
    """Adapt L3-L5 JSON artifacts into a stable, queryable local index."""

    root = Path(repository_root)
    ensure_source_allowed(root, allow_legacy_source=allow_legacy_source)
    graph = _as_list(_read_json(root / "data/processed/l3/integrated_shannon_graph.json"))
    conflict_edges = _as_list(
        _read_json(root / "data/processed/l3/conflict_edges.json"), ("conflict_edges",)
    )
    contexts = _as_list(
        _read_json(root / "data/processed/l4/context_mentions.json"), ("context_mentions",)
    )
    validation = _as_list(
        _read_json(root / "data/processed/l5/validation_results.json"), ("validation_results",)
    )
    hypotheses = _load_hypotheses(root)

    triples: List[Dict[str, Any]] = []
    pairs: Dict[str, Dict[str, Any]] = {}
    entities = set()
    used_compatibility_fallback = False
    for edge in graph:
        subject, subject_fallback = _normalized_value(edge, "subject")
        obj, object_fallback = _normalized_value(edge, "object")
        used_compatibility_fallback |= subject_fallback or object_fallback
        if not subject or not obj:
            continue
        key = _pair_key(subject, obj)
        entities.update((subject, obj))
        pairs.setdefault(key, {"subject": subject, "object": obj, "triple_ids": []})
        for trace in edge.get("whitebox_traceability", []):
            if not isinstance(trace, dict):
                continue
            triple = {
                **trace,
                "triple_id": str(trace.get("triple_id") or trace.get("evidence_id") or ""),
                "subject": subject,
                "object": obj,
                "relation_sign": int(trace.get("relation_sign", 0)),
                "normalization_source": "v2" if not (subject_fallback or object_fallback) else "legacy_canonical_fallback",
            }
            triples.append(triple)
            if triple["triple_id"]:
                pairs[key]["triple_ids"].append(triple["triple_id"])

    normalized_conflicts = []
    for edge in conflict_edges:
        subject, subject_fallback = _normalized_value(edge, "subject")
        obj, object_fallback = _normalized_value(edge, "object")
        used_compatibility_fallback |= subject_fallback or object_fallback
        normalized_conflicts.append({**edge, "source": subject, "target": obj, "pair_key": _pair_key(subject, obj)})
        entities.update(item for item in (subject, obj) if item)

    hypothesis_pairs: Dict[str, str] = {}
    for hypothesis in hypotheses:
        seed = str(hypothesis.get("seed_pair") or "")
        if "->" in seed:
            subject, obj = (part.strip() for part in seed.split("->", 1))
            hypothesis_pairs[str(hypothesis.get("hypothesis_id", ""))] = _pair_key(subject, obj)
        elif len(hypothesis.get("core_path", [])) >= 2:
            path = hypothesis["core_path"]
            hypothesis_pairs[str(hypothesis.get("hypothesis_id", ""))] = _pair_key(path[0], path[-1])

    store = {
        "schema_version": "query_knowledge_store_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "knowledge_store_status": (
            "built_from_legacy_runtime" if allow_legacy_source
            else "built_from_current_runtime"
        ),
        "runtime_data_status": "runtime_graph_available" if graph else "no_graph_runtime_data",
        "using_legacy_data": allow_legacy_source,
        "entities": sorted(entities),
        "triples": triples,
        "pairs": pairs,
        "conflict_edges": normalized_conflicts,
        "context_mentions": contexts,
        "validation_results": validation,
        "hypotheses": hypotheses,
        "hypothesis_pairs": hypothesis_pairs,
        "warnings": (
            (["Explicit legacy knowledge-store source is in use."] if allow_legacy_source else [])
            + (["v2 normalized fields unavailable for some records; canonical/uppercase compatibility fallback used."] if used_compatibility_fallback else [])
        ),
    }
    target = Path(output_path) if output_path else root / DEFAULT_STORE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    return store


def load_knowledge_store(
    path: str | Path = DEFAULT_STORE_PATH,
    *,
    build_if_missing: bool = False,
    repository_root: str | Path = ".",
    allow_legacy_source: bool = False,
) -> Dict[str, Any]:
    """Load a store, returning an explicit empty state when it is absent."""

    store_path = Path(path)
    if not store_path.is_absolute():
        store_path = Path(repository_root) / store_path
    ensure_source_allowed(store_path, allow_legacy_source=allow_legacy_source)
    if not store_path.exists():
        if build_if_missing:
            return build_knowledge_store(
                repository_root,
                output_path=store_path,
                allow_legacy_source=allow_legacy_source,
            )
        return empty_knowledge_store()
    store = _read_json(store_path)
    if not isinstance(store, dict) or not store:
        return empty_knowledge_store("invalid_empty_store")
    store.setdefault("knowledge_store_status", "loaded_current_runtime")
    store.setdefault("runtime_data_status", "runtime_graph_available" if store.get("triples") else "no_graph_runtime_data")
    store["using_legacy_data"] = is_legacy_source(store_path)
    store.setdefault("warnings", [])
    if store["using_legacy_data"]:
        store["warnings"].append("Explicit legacy knowledge-store source is in use.")
    return store


def query_exact_pair(subject: str, obj: str, store: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    active = store if store is not None else load_knowledge_store()
    triple_ids = set(active.get("pairs", {}).get(_pair_key(subject, obj), {}).get("triple_ids", []))
    return [triple for triple in active.get("triples", []) if triple.get("triple_id") in triple_ids]


def query_neighbors(entity: str, max_depth: int = 1, store: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    active = store if store is not None else load_knowledge_store()
    frontier = {str(entity).upper().strip()}
    visited = set(frontier)
    results: List[Dict[str, Any]] = []
    seen_pairs = set()
    for _ in range(max(0, max_depth)):
        next_frontier = set()
        for pair_key, pair in active.get("pairs", {}).items():
            if pair["subject"] in frontier or pair["object"] in frontier:
                if pair_key not in seen_pairs:
                    results.append(pair)
                    seen_pairs.add(pair_key)
                next_frontier.update((pair["subject"], pair["object"]))
        frontier = next_frontier - visited
        visited.update(next_frontier)
        if not frontier:
            break
    return results


def query_contexts_for_pair(subject: str, obj: str, store: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    active = store if store is not None else load_knowledge_store()
    triple_ids = {item.get("triple_id") for item in query_exact_pair(subject, obj, active)}
    return [item for item in active.get("context_mentions", []) if item.get("triple_id") in triple_ids]


def query_conflicts_for_pair(subject: str, obj: str, store: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    active = store if store is not None else load_knowledge_store()
    key = _pair_key(subject, obj)
    return [item for item in active.get("conflict_edges", []) if item.get("pair_key") == key]


def query_validation_for_pair(subject: str, obj: str, store: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    active = store if store is not None else load_knowledge_store()
    key = _pair_key(subject, obj)
    hypothesis_ids = {hid for hid, pair_key in active.get("hypothesis_pairs", {}).items() if pair_key == key}
    return [item for item in active.get("validation_results", []) if item.get("hypothesis_id") in hypothesis_ids]


def query_hypotheses_for_pair(subject: str, obj: str, store: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    active = store if store is not None else load_knowledge_store()
    key = _pair_key(subject, obj)
    hypothesis_ids = {hid for hid, pair_key in active.get("hypothesis_pairs", {}).items() if pair_key == key}
    return [item for item in active.get("hypotheses", []) if item.get("hypothesis_id") in hypothesis_ids]
