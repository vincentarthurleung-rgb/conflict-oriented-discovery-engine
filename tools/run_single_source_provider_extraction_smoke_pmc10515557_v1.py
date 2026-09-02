#!/usr/bin/env python3
"""One-shot billing boundary for the authorized PMC10515557 extraction smoke."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any
import xml.etree.ElementTree as ET

from code_engine.extraction.client_factory import build_json_client_from_config, resolve_l1_provider_settings
from code_engine.extraction.deepseek_client import DeepSeekExtractionError
from code_engine.fulltext.fulltext_l1_v2 import (
    DEFAULT_MAX_TOKENS, DEFAULT_THINKING_MODE, PROMPT_VERSION, SCHEMA_VERSION,
    build_prompt, cache_key, estimate_tokens, formal_schema_hash, prompt_hash, schema_hash,
)
from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import (
    COMPLETENESS_POLICY_VERSION, HYDRATOR_VERSION,
)
from code_engine.fulltext.experimental_semantics_registry import REGISTRY_VERSION
from code_engine.fulltext.evidence_anchors import EVIDENCE_ANCHOR_VERSION
from code_engine.schemas.fulltext_observation_draft import DRAFT_SCHEMA_VERSION
from code_engine.validation.external_api_smoke import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260902_single_source_provider_extraction_smoke_pmc10515557_v1"
ART = RUN / "artifacts"
REQUEST_ASSETS = RUN / "provider_request_assets"
SOURCE = ROOT / "runs/20260827_proposition_driven_targeted_network_discovery_smoke_v1/retrieval_assets/45b8c00ad24ef8f5/fulltext/PMC10515557.xml"
SPEC = ROOT / "runs/20260826_proposition_driven_targeted_expansion_protocol_v1_offline/artifacts/targeted_retrieval_specifications_v1.jsonl"
EXPECTED_SOURCE_HASH = "dd1152fd25d1d707b456bf2e29746ccd9befee76b312bfe63cb29061cec176ce"
TARGET_ID = "future_proposition_target_v1:45b8c00ad24ef8f5"
PROVIDER = "deepseek"
MODEL = "deepseek-v4-pro"
BLOCK_ID = "PMC10515557_target_45b8c00ad24ef8f5_0"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value: bytes | str | Path) -> str:
    if isinstance(value, Path): data = value.read_bytes()
    elif isinstance(value, str): data = value.encode("utf-8")
    else: data = value
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_target() -> dict[str, Any]:
    rows = [json.loads(line) for line in SPEC.read_text(encoding="utf-8").splitlines() if line]
    return next(row for row in rows if row["target_id"] == TARGET_ID)


def section_paragraphs() -> dict[str, list[str]]:
    root = ET.fromstring(SOURCE.read_bytes())
    output: dict[str, list[str]] = {}
    for section in root.findall(".//body//sec"):
        title_node = section.find("title")
        title = " ".join("".join(title_node.itertext()).split()) if title_node is not None else ""
        output[title] = [" ".join("".join(p.itertext()).split()) for p in section.findall("./p")]
    return output


def build_source_block() -> str:
    sections = section_paragraphs()
    cohort = sections["Clinicopathological features of neuroblastoma patients"][0]
    statistics = sections["Statistical analysis"][0]
    patient = sections["Patient characteristics"][0]
    expression = sections["Analysis of TRIB3 expression in NB tissues"][0]
    survival = sections["Survival analysis of TRIB3"]
    lines = [
        "PRECEDING_SETUP: " + cohort,
        "LINKED_METHODS: " + statistics,
        "CURRENT_RESULTS: " + patient,
        "CURRENT_RESULTS: " + expression,
        *("CURRENT_RESULTS: " + paragraph for paragraph in survival),
    ]
    return "\n".join(lines)


def request_material() -> tuple[dict[str, Any], dict[str, Any], str, str, str]:
    target = load_target()
    block_text = build_source_block()
    paper = {
        "paper_id": "pmid:37744426", "pmid": "37744426", "pmcid": "PMC10515557",
        "doi": "10.1177/11795549231199926", "subject": "TRIB3",
        "object": "overall survival", "conflict_relation": "comparison",
        "abstract_observation_ids": [],
    }
    block = {
        "block_id": BLOCK_ID, "parent_block_id": BLOCK_ID, "child_block_id": None,
        "text": block_text, "chunk_hash": digest(block_text),
        "section": {"section_title": "Results", "section_type": "results"},
        "paper_metadata": {"pmid": "37744426", "pmcid": "PMC10515557"},
    }
    prompt = build_prompt(paper, block)
    config = {
        "target_id": TARGET_ID, "target_specification_sha256": digest(SPEC),
        "prompt_version": PROMPT_VERSION, "prompt_hash": prompt_hash(),
        "draft_schema_version": DRAFT_SCHEMA_VERSION, "draft_schema_hash": schema_hash(),
        "formal_schema_version": SCHEMA_VERSION, "formal_schema_hash": formal_schema_hash(),
        "hydrator_version": HYDRATOR_VERSION, "semantics_registry_version": REGISTRY_VERSION,
        "evidence_anchor_version": EVIDENCE_ANCHOR_VERSION,
        "completeness_policy_version": COMPLETENESS_POLICY_VERSION,
        "provider": PROVIDER, "model": MODEL, "thinking_mode": DEFAULT_THINKING_MODE,
        "max_tokens": DEFAULT_MAX_TOKENS, "temperature": 0, "top_p": 1,
        "maximum_attempts": 1, "automatic_retries": 0,
    }
    config_hash = digest(json.dumps(config, sort_keys=True, separators=(",", ":")))
    candidate_hash = digest(json.dumps({"subject": paper["subject"], "object": paper["object"], "target_id": TARGET_ID}, sort_keys=True))
    identity = cache_key(source_fulltext_hash=EXPECTED_SOURCE_HASH, chunk_hash=block["chunk_hash"], provider=PROVIDER, model=MODEL, config_hash=config_hash, candidate_prior_hash=candidate_hash, thinking_mode=DEFAULT_THINKING_MODE, max_tokens=DEFAULT_MAX_TOKENS)
    return paper, block, prompt, identity, config_hash


def prepare() -> None:
    ART.mkdir(parents=True, exist_ok=True); REQUEST_ASSETS.mkdir(parents=True, exist_ok=True)
    actual_hash = digest(SOURCE)
    if actual_hash != EXPECTED_SOURCE_HASH:
        raise RuntimeError(f"source_hash_mismatch:{actual_hash}")
    target = load_target()
    paper, block, prompt, identity, config_hash = request_material()
    source_payload = REQUEST_ASSETS / "source_payload_sent.txt"
    rendered_prompt = REQUEST_ASSETS / "rendered_prompt.txt"
    source_payload.write_text(block["text"], encoding="utf-8")
    rendered_prompt.write_text(prompt, encoding="utf-8")
    cache_matches = sorted(str(path.relative_to(ROOT)) for path in ROOT.glob(f"runs/**/{identity}.json") if RUN not in path.parents)
    source_matches = subprocess.run(["rg", "-l", "-F", EXPECTED_SOURCE_HASH, "runs", "--glob", "*.json", "--glob", "*.jsonl"], cwd=ROOT, capture_output=True, text=True, check=False).stdout.splitlines()
    sufficient = [path for path in source_matches if "20260827_proposition_driven_targeted_network_discovery_smoke_v1" not in path and RUN.name not in path]
    write_json(ART / "baseline.json", {"schema_version": "single_source_provider_extraction_smoke_v1_baseline", "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip(), "target_id": TARGET_ID, "source_pmid": "37744426", "source_pmcid": "PMC10515557", "source_doi": "10.1177/11795549231199926", "historical_candidate_object_count": 11, "formal_conflict_count": 0, "entity_integrity_claims_blocked": 241, "entity_integrity_signals_blocked": 2})
    write_json(ART / "source_snapshot_verification.json", {"schema_version": "source_snapshot_verification_v1", "source_path": relative(SOURCE), "expected_sha256": EXPECTED_SOURCE_HASH, "actual_sha256": actual_hash, "hash_matches": True, "paper_redownloaded": False, "usable": True})
    write_json(ART / "cache_preflight.json", {"schema_version": "single_source_extraction_cache_preflight_v1", "cache_identity": identity, "source_sha256": actual_hash, "exact_cache_identity_matches": cache_matches, "other_source_hash_references": source_matches, "sufficient_compatible_cache_matches": sufficient, "cache_hit": bool(cache_matches), "sufficient_cache_hit": bool(cache_matches), "provider_call_required": not cache_matches, "cache_checked_before_provider": True})
    write_json(ART / "provider_execution_authorization.json", {"schema_version": "single_source_provider_execution_authorization_v1", "execution_authorized": True, "authorization_scope": TARGET_ID, "source_pmcid": "PMC10515557", "maximum_provider_calls": 1, "maximum_provider_attempts": 1, "automatic_retries": 0, "authorization_received": True, "contradiction_evaluation_authorized": False, "candidate_qualification_authorized": False, "l4_or_formal_adjudication_authorized": False})
    write_json(ART / "rendered_extraction_contract.json", {"schema_version": "rendered_extraction_contract_manifest_v1", "target_specification": target, "prompt_version": PROMPT_VERSION, "prompt_contract_hash": prompt_hash(), "rendered_prompt_path": relative(rendered_prompt), "rendered_prompt_sha256": digest(rendered_prompt), "rendered_prompt_character_count": len(prompt), "estimated_input_tokens": estimate_tokens(prompt), "draft_schema_version": DRAFT_SCHEMA_VERSION, "draft_schema_hash": schema_hash(), "formal_schema_version": SCHEMA_VERSION, "formal_schema_hash": formal_schema_hash(), "source_specific_prompt_created": False, "authoritative_generic_prompt_used": True})
    write_json(ART / "provider_request_manifest.json", {"schema_version": "single_source_provider_request_manifest_v1", "request_identity": identity, "status": "prepared", "prepared_timestamp": now(), "target_id": TARGET_ID, "provider": PROVIDER, "model": MODEL, "parameters": {"temperature": 0, "top_p": 1, "max_tokens": DEFAULT_MAX_TOKENS, "thinking_mode": DEFAULT_THINKING_MODE, "retry_on_length": False}, "maximum_attempts": 1, "automatic_retries": 0, "source_fulltext_path": relative(SOURCE), "source_fulltext_sha256": actual_hash, "source_payload_sent_path": relative(source_payload), "source_payload_sent_sha256": digest(source_payload), "rendered_prompt_path": relative(rendered_prompt), "rendered_prompt_sha256": digest(rendered_prompt), "block": {k: block[k] for k in ("block_id", "parent_block_id", "child_block_id", "chunk_hash", "section")}, "paper_identity": {k: paper[k] for k in ("paper_id", "pmid", "pmcid", "doi")}, "config_hash": config_hash, "credential_values_logged": False, "request_sent": False, "provider_attempts": 0})
    if cache_matches:
        raise RuntimeError("sufficient_cache_hit_reuse_required")


def execute_once() -> None:
    attempt_path = ART / "provider_attempt_ledger.json"
    raw_path = ART / "raw_provider_response.txt"
    if attempt_path.exists():
        raise RuntimeError("provider_attempt_already_recorded_refusing_second_call")
    manifest = read_json(ART / "provider_request_manifest.json")
    if manifest["status"] != "prepared" or manifest["provider_attempts"] != 0:
        raise RuntimeError("provider_request_not_in_prepared_zero_attempt_state")
    if read_json(ART / "cache_preflight.json")["sufficient_cache_hit"]:
        raise RuntimeError("cache_hit_refuses_provider_call")
    source_payload = ROOT / manifest["source_payload_sent_path"]
    rendered_prompt = ROOT / manifest["rendered_prompt_path"]
    if digest(SOURCE) != EXPECTED_SOURCE_HASH or digest(source_payload) != manifest["source_payload_sent_sha256"] or digest(rendered_prompt) != manifest["rendered_prompt_sha256"]:
        raise RuntimeError("frozen_request_asset_hash_mismatch")
    load_dotenv()
    settings = resolve_l1_provider_settings(provider=PROVIDER, model_name=MODEL, thinking_mode=DEFAULT_THINKING_MODE, max_tokens=DEFAULT_MAX_TOKENS)
    client = build_json_client_from_config(PROVIDER, MODEL, max_retries=0)
    if client is None:
        raise RuntimeError("provider_not_configured_before_attempt")
    started = now()
    write_json(attempt_path, {"schema_version": "single_source_provider_attempt_ledger_v1", "request_identity": manifest["request_identity"], "status": "attempt_started", "attempt_number": 1, "started_timestamp": started, "maximum_attempts": 1, "automatic_retries": 0, "raw_response_path": relative(raw_path), "raw_response_persisted_before_parser": False})
    manifest.update({"status": "attempt_started", "request_sent": True, "provider_attempts": 1, "attempt_started_timestamp": started})
    write_json(ART / "provider_request_manifest.json", manifest)
    raw_written = False
    def raw_sink(payload: bytes) -> None:
        nonlocal raw_written
        raw_path.write_bytes(payload)
        raw_written = True
    try:
        result = client.extract_json_result(rendered_prompt.read_text(encoding="utf-8"), model=MODEL, temperature=0, top_p=1, max_tokens=DEFAULT_MAX_TOKENS, retry_on_length=False, thinking_mode=DEFAULT_THINKING_MODE, raw_response_sink=raw_sink)
        if not raw_written or not raw_path.is_file():
            raise RuntimeError("raw_response_sink_invariant_failed")
        write_json(ART / "raw_provider_response_manifest.json", {"schema_version": "raw_provider_response_manifest_v1", "request_identity": manifest["request_identity"], "raw_response_path": relative(raw_path), "raw_response_sha256": digest(raw_path), "raw_response_bytes": raw_path.stat().st_size, "persisted": True, "persisted_before_scientific_parser_or_validator": True, "provider": PROVIDER, "model": MODEL, "timestamp": now()})
        transport = {"finish_reason": result.finish_reason, "usage": result.usage, "attempt_count": result.attempt_count, **result.provider_metadata}
        write_json(ART / "provider_call_result.json", {"schema_version": "single_source_provider_call_result_v1", "status": "response_received_and_transport_parsed", "request_identity": manifest["request_identity"], "provider": PROVIDER, "model": MODEL, "transport_metadata": transport, "parsed_payload": result.payload})
        write_json(attempt_path, {"schema_version": "single_source_provider_attempt_ledger_v1", "request_identity": manifest["request_identity"], "status": "response_received", "attempt_number": 1, "started_timestamp": started, "completed_timestamp": now(), "maximum_attempts": 1, "automatic_retries": 0, "raw_response_path": relative(raw_path), "raw_response_persisted_before_parser": True, "provider_error": None})
    except DeepSeekExtractionError as exc:
        if raw_written and raw_path.is_file():
            write_json(ART / "raw_provider_response_manifest.json", {"schema_version": "raw_provider_response_manifest_v1", "request_identity": manifest["request_identity"], "raw_response_path": relative(raw_path), "raw_response_sha256": digest(raw_path), "raw_response_bytes": raw_path.stat().st_size, "persisted": True, "persisted_before_scientific_parser_or_validator": True, "provider": PROVIDER, "model": MODEL, "timestamp": now()})
        write_json(attempt_path, {"schema_version": "single_source_provider_attempt_ledger_v1", "request_identity": manifest["request_identity"], "status": "provider_or_transport_failure", "attempt_number": 1, "started_timestamp": started, "completed_timestamp": now(), "maximum_attempts": 1, "automatic_retries": 0, "raw_response_path": relative(raw_path) if raw_path.exists() else None, "raw_response_persisted_before_parser": raw_path.exists(), "provider_error": {"error_kind": exc.error_kind, "finish_reason": exc.finish_reason, "status_code": exc.status_code, "message": "deepseek_extraction_failed"}})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--prepare", action="store_true"); parser.add_argument("--execute-once", action="store_true")
    selected = parser.parse_args()
    if selected.prepare == selected.execute_once:
        raise SystemExit("select exactly one of --prepare or --execute-once")
    prepare() if selected.prepare else execute_once()


if __name__ == "__main__":
    main()
