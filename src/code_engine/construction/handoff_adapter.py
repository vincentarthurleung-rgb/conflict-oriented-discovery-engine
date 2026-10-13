"""Fail-closed adapter from a verified prospective handoff to construction input.

The adapter does not admit sources, retrieve content, or perform scientific
inference.  It verifies an already-frozen prospective handoff, reuses the
frozen ConstructionEvidenceDocumentV1 constructor, and keeps public source
identity in controller-only provenance.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import secrets
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts import search_plan_v24_alpha318a1_source_contracts as construction
from scripts import search_plan_v24_alpha318a3_correction_reference as correction
from scripts import search_plan_v24_alpha318a6_license_extraction as license_policy
from scripts import search_plan_v24_alpha321_body_only as body_policy
from scripts import search_plan_v24_alpha321_jats_primary_identity_v2 as identity_policy


TOKEN_AUTHORITY_PATH = "scripts/run_search_plan_v24_alpha319d_pmc_oa_jats_construction_eligibility.py"
TOKEN_AUTHORITY_SHA256 = "277c3b3c0fc02b2b0e44cf2320923b19755df2477b7c38ae7d3824542d3c26ef"
TOKEN_AUTHORITY_EXPRESSION = 'token = "src_" + secrets.token_hex(32)'
CONSTRUCTION_IMPLEMENTATION_PATH = "scripts/search_plan_v24_alpha318a1_source_contracts.py"
CONSTRUCTION_IMPLEMENTATION_SHA256 = "88c4370ebe45c157f9501ea1c7e6350f0348d67a15463254be68d8c315546c5e"
BODY_IMPLEMENTATION_PATH = "scripts/search_plan_v24_alpha321_body_only.py"
BODY_IMPLEMENTATION_SHA256 = "86b63eba8e19df97c1431204261378abf685269d2b4c04f96803104c93bd91da"
IDENTITY_IMPLEMENTATION_PATH = "scripts/search_plan_v24_alpha321_jats_primary_identity_v2.py"
IDENTITY_IMPLEMENTATION_SHA256 = "4a33e0be976f4dd1af1b5f498a9d484e4e45b8ffae70c06d172d7fbff2d4db2a"
LICENSE_IMPLEMENTATION_PATH = "scripts/search_plan_v24_alpha318a6_license_extraction.py"
LICENSE_IMPLEMENTATION_SHA256 = "c4c18cea73e5714ce6107c655805a5772c27c608af13b30d95e1a0659c17e415"
NORMALIZATION = "Unicode NFKC; whitespace collapsed within paragraphs; two LF between paragraphs"


class AdapterValidationError(ValueError):
    """A stable, fail-closed adapter rejection."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise AdapterValidationError(reason)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _strict_json(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            _require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: _require(False, "NONFINITE_JSON"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AdapterValidationError("INVALID_JSON") from exc


def _read_physical(path: Path) -> bytes:
    absolute = path.absolute()
    _require(absolute.is_file(), "ARTIFACT_NOT_FILE:" + str(path))
    _require(not any(item.is_symlink() for item in (absolute, *absolute.parents)),
             "SYMLINK_FORBIDDEN:" + str(path))
    return absolute.read_bytes()


def root_hash(directory: Path, marker: str) -> str:
    directory = directory.absolute()
    _require(directory.is_dir(), "ROOT_DIRECTORY_MISSING:" + str(directory))
    paths = sorted(directory.rglob("*"))
    _require(not any(path.is_symlink() for path in paths),
             "FROZEN_ROOT_SYMLINK_FORBIDDEN:" + str(directory))
    entries = [[path.relative_to(directory).as_posix(), sha256(_read_physical(path))]
               for path in paths if path.is_file() and path.name != marker]
    return sha256(canonical(entries))


@dataclass(frozen=True)
class AdapterConfig:
    repository_root: Path
    pilot_directory: str
    pilot_marker: str
    pilot_root_sha256: str
    handoff_sha256: str
    smoke_directory: str
    smoke_marker: str
    smoke_root_sha256: str
    release_directory: str
    release_marker: str
    release_root_sha256: str
    source_id: str
    pmid: str
    pmcid: str
    doi: str | None

    @property
    def expected_identity(self) -> dict[str, str | None]:
        return {"source_id": self.source_id, "pmid": self.pmid,
                "pmcid": self.pmcid, "doi": self.doi}


def _verify_root(repository_root: Path, relative: str, marker: str,
                 expected: str) -> dict[str, Any]:
    directory = (repository_root / relative).absolute()
    marker_path = directory / marker
    recorded = _read_physical(marker_path).decode("ascii").strip()
    actual = root_hash(directory, marker)
    _require(actual == recorded == expected, "AUTHORITATIVE_ROOT_MISMATCH:" + relative)
    return {"path": relative, "marker": marker, "sha256": actual, "verified": True}


def verify_authoritative_roots(config: AdapterConfig) -> list[dict[str, Any]]:
    root = config.repository_root.absolute()
    return [
        _verify_root(root, config.smoke_directory, config.smoke_marker,
                     config.smoke_root_sha256),
        _verify_root(root, config.pilot_directory, config.pilot_marker,
                     config.pilot_root_sha256),
        _verify_root(root, config.release_directory, config.release_marker,
                     config.release_root_sha256),
    ]


def _resolve_reference(repository_root: Path, pilot_directory: Path,
                       reference: dict[str, Any], reason: str) -> tuple[Path, bytes]:
    _require(type(reference) is dict and set(reference) >= {"artifact_path", "sha256"},
             reason + ":REFERENCE_SHAPE")
    path = Path(reference["artifact_path"])
    path = path if path.is_absolute() else repository_root / path
    resolved = path.absolute()
    try:
        resolved.relative_to(pilot_directory.absolute())
    except ValueError as exc:
        raise AdapterValidationError(reason + ":REFERENCE_OUTSIDE_PILOT") from exc
    raw = _read_physical(resolved)
    _require(sha256(raw) == reference["sha256"], reason + ":SHA256_MISMATCH")
    if "byte_count" in reference:
        _require(len(raw) == reference["byte_count"], reason + ":BYTE_COUNT_MISMATCH")
    return resolved, raw


def _load_json_reference(repository_root: Path, pilot_directory: Path,
                         reference: dict[str, Any], reason: str) -> tuple[Path, dict[str, Any]]:
    path, raw = _resolve_reference(repository_root, pilot_directory, reference, reason)
    value = _strict_json(raw)
    _require(type(value) is dict, reason + ":JSON_OBJECT_REQUIRED")
    return path, value


def _journal_events(raw: bytes, manifest_sha256: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    previous = manifest_sha256
    for sequence, line in enumerate(raw.splitlines(), 1):
        event = _strict_json(line)
        _require(type(event) is dict and event.get("sequence_number") == sequence,
                 "JOURNAL_SEQUENCE_INVALID")
        _require(event.get("previous_entry_hash") == previous, "JOURNAL_CHAIN_INVALID")
        base = {key: value for key, value in event.items() if key != "entry_hash"}
        # JournalEventV2 uses its own newline-terminated canonical encoding.
        _require(sha256(canonical(base) + b"\n") == event.get("entry_hash"),
                 "JOURNAL_ENTRY_HASH_INVALID")
        previous = event["entry_hash"]
        events.append(event)
    _require(bool(events), "JOURNAL_EMPTY")
    return events


def load_verified_evidence_bundle(config: AdapterConfig) -> dict[str, Any]:
    roots = verify_authoritative_roots(config)
    repository_root = config.repository_root.absolute()
    pilot = (repository_root / config.pilot_directory).absolute()
    handoff_path = pilot / "journal/handoff.json"
    handoff_raw = _read_physical(handoff_path)
    _require(sha256(handoff_raw) == config.handoff_sha256, "HANDOFF_SHA256_MISMATCH")
    handoff = _strict_json(handoff_raw)
    _require(type(handoff) is dict, "HANDOFF_OBJECT_REQUIRED")
    _require(handoff.get("schema_version") == "ProspectiveAuthoritativeHandoffV1",
             "HANDOFF_SCHEMA_MISMATCH")
    _require(handoff.get("historical_evidence") is False and
             handoff.get("scientific_result") is False, "HANDOFF_BOUNDARY_MISMATCH")
    sources = handoff.get("sources")
    _require(type(sources) is list and len(sources) == 1, "HANDOFF_SOURCE_COUNT_MISMATCH")
    source_handoff = sources[0]

    _, source = _load_json_reference(repository_root, pilot,
                                     source_handoff.get("source_reference"),
                                     "SOURCE_REFERENCE")
    _, gates = _load_json_reference(repository_root, pilot,
                                    source_handoff.get("gates"), "GATES_REFERENCE")
    _, capture = _load_json_reference(repository_root, pilot,
                                      source_handoff.get("capture"), "CAPTURE_REFERENCE")
    _, raw_jats = _resolve_reference(repository_root, pilot,
                                    source_handoff.get("raw_artifact"), "RAW_JATS_REFERENCE")
    outputs = source_handoff.get("outputs")
    _require(type(outputs) is dict, "HANDOFF_OUTPUTS_MISSING")
    _, normalized_jats = _resolve_reference(repository_root, pilot,
        outputs.get("normalized_jats"), "NORMALIZED_JATS_REFERENCE")
    _, canonical_body = _resolve_reference(repository_root, pilot,
        outputs.get("canonical_body"), "CANONICAL_BODY_REFERENCE")
    _, barrier = _load_json_reference(repository_root, pilot, handoff.get("barrier"),
                                      "BARRIER_REFERENCE")
    _, activation = _load_json_reference(repository_root, pilot, handoff.get("activation"),
                                         "ACTIVATION_REFERENCE")
    _, configuration = _load_json_reference(repository_root, pilot,
        handoff.get("configuration"), "CONFIGURATION_REFERENCE")

    evidence_index_path = pilot / "journal/evidence_index.json"
    evidence_index_raw = _read_physical(evidence_index_path)
    evidence_index = _strict_json(evidence_index_raw)
    _require(type(evidence_index) is dict, "EVIDENCE_INDEX_OBJECT_REQUIRED")
    manifest_ref = evidence_index.get("manifest")
    _, manifest_raw = _resolve_reference(repository_root, pilot, manifest_ref,
                                         "REQUEST_MANIFEST_REFERENCE")
    _require(sha256(manifest_raw) == handoff.get("manifest_sha256"),
             "HANDOFF_MANIFEST_SHA256_MISMATCH")
    journal_ref = evidence_index.get("journal")
    _, journal_raw = _resolve_reference(repository_root, pilot, journal_ref,
                                        "JOURNAL_REFERENCE")
    journal = _journal_events(journal_raw, handoff["manifest_sha256"])

    return {
        "roots": roots,
        "pilot_root_sha256": config.pilot_root_sha256,
        "handoff_sha256": config.handoff_sha256,
        "handoff_reference": {"artifact_path": str(handoff_path),
                              "sha256": sha256(handoff_raw),
                              "byte_count": len(handoff_raw)},
        "handoff": handoff,
        "source": source,
        "source_reference": copy.deepcopy(source_handoff["source_reference"]),
        "gates": gates,
        "gate_reference": copy.deepcopy(source_handoff["gates"]),
        "capture": capture,
        "capture_reference": copy.deepcopy(source_handoff["capture"]),
        "barrier": barrier,
        "activation": activation,
        "configuration": configuration,
        "evidence_index": evidence_index,
        "evidence_index_sha256": sha256(evidence_index_raw),
        "journal": journal,
        "raw_jats": raw_jats,
        "raw_jats_reference": copy.deepcopy(source_handoff["raw_artifact"]),
        "normalized_jats": normalized_jats,
        "normalized_jats_reference": copy.deepcopy(outputs["normalized_jats"]),
        "canonical_body": canonical_body,
        "canonical_body_reference": copy.deepcopy(outputs["canonical_body"]),
        "expected_identity": config.expected_identity,
        "policy_bindings": {
            CONSTRUCTION_IMPLEMENTATION_PATH: CONSTRUCTION_IMPLEMENTATION_SHA256,
            BODY_IMPLEMENTATION_PATH: BODY_IMPLEMENTATION_SHA256,
            IDENTITY_IMPLEMENTATION_PATH: IDENTITY_IMPLEMENTATION_SHA256,
            LICENSE_IMPLEMENTATION_PATH: LICENSE_IMPLEMENTATION_SHA256,
        },
    }


def issue_opaque_source_token(config: AdapterConfig) -> dict[str, Any]:
    """Issue one controller-private token using the frozen CSPRNG authority."""
    authority_path = config.repository_root.absolute() / TOKEN_AUTHORITY_PATH
    authority_raw = _read_physical(authority_path)
    _require(sha256(authority_raw) == TOKEN_AUTHORITY_SHA256,
             "OPAQUE_TOKEN_AUTHORITY_SOURCE_MISMATCH")
    _require(TOKEN_AUTHORITY_EXPRESSION in authority_raw.decode("utf-8"),
             "OPAQUE_TOKEN_AUTHORITY_EXPRESSION_MISSING")
    token = "src_" + secrets.token_hex(32)
    return {
        "schema_version": "OpaqueSourceTokenAuthorityV1",
        "visibility": "CONTROLLER_PRIVATE_NOT_MODEL_VISIBLE_WITH_SOURCE_MAPPING",
        "generation": {
            "mechanism": "secrets.token_hex(32)",
            "random_byte_count": 32,
            "entropy_bits_nominal": 256,
            "authority_source_path": TOKEN_AUTHORITY_PATH,
            "authority_source_sha256": TOKEN_AUTHORITY_SHA256,
            "derived_from_source_identity": False,
        },
        "binding": {
            "pilot_root_sha256": config.pilot_root_sha256,
            "handoff_sha256": config.handoff_sha256,
            **config.expected_identity,
        },
        "opaque_source_token": token,
        "opaque_source_token_sha256": sha256(token.encode("ascii")),
    }


def validate_opaque_source_token(record: dict[str, Any] | None,
                                 bundle: dict[str, Any], repository_root: Path) -> str:
    _require(record is not None, "MISSING_OPAQUE_SOURCE_TOKEN_AUTHORITY")
    _require(type(record) is dict and record.get("schema_version") ==
             "OpaqueSourceTokenAuthorityV1", "OPAQUE_SOURCE_TOKEN_AUTHORITY_SCHEMA_INVALID")
    token = record.get("opaque_source_token")
    _require(type(token) is str and re.fullmatch(r"src_[0-9a-f]{64}", token) is not None,
             "OPAQUE_SOURCE_TOKEN_INVALID")
    _require(record.get("opaque_source_token_sha256") == sha256(token.encode("ascii")),
             "OPAQUE_SOURCE_TOKEN_RECORD_HASH_MISMATCH")
    generation = record.get("generation")
    _require(type(generation) is dict and
             generation.get("mechanism") == "secrets.token_hex(32)" and
             generation.get("random_byte_count") == 32 and
             generation.get("entropy_bits_nominal") == 256 and
             generation.get("derived_from_source_identity") is False and
             generation.get("authority_source_path") == TOKEN_AUTHORITY_PATH and
             generation.get("authority_source_sha256") == TOKEN_AUTHORITY_SHA256,
             "OPAQUE_SOURCE_TOKEN_AUTHORITY_INVALID")
    authority_raw = _read_physical(repository_root.absolute() / TOKEN_AUTHORITY_PATH)
    _require(sha256(authority_raw) == TOKEN_AUTHORITY_SHA256 and
             TOKEN_AUTHORITY_EXPRESSION in authority_raw.decode("utf-8"),
             "OPAQUE_SOURCE_TOKEN_AUTHORITY_SOURCE_MISMATCH")
    expected_binding = {
        "pilot_root_sha256": bundle["pilot_root_sha256"],
        "handoff_sha256": bundle["handoff_sha256"],
        **bundle["expected_identity"],
    }
    _require(record.get("binding") == expected_binding,
             "OPAQUE_SOURCE_TOKEN_BINDING_MISMATCH")
    _require(record.get("visibility") ==
             "CONTROLLER_PRIVATE_NOT_MODEL_VISIBLE_WITH_SOURCE_MAPPING",
             "OPAQUE_SOURCE_TOKEN_VISIBILITY_MISMATCH")
    return token


def validate_construction_document(document: dict[str, Any], token: str) -> None:
    top_keys = {"schema_version", "abstract_text", "body_text", "paragraphs",
                "article_title_visible", "bibliography_visible", "normalization"}
    _require(type(document) is dict and set(document) == top_keys,
             "CONSTRUCTION_DOCUMENT_FIELDS_INVALID")
    _require(document["schema_version"] == "ConstructionEvidenceDocumentV1",
             "CONSTRUCTION_DOCUMENT_SCHEMA_INVALID")
    _require(document["article_title_visible"] is False and
             document["bibliography_visible"] is False,
             "CONSTRUCTION_DOCUMENT_VISIBILITY_INVALID")
    _require(type(document["abstract_text"]) is str and
             len(document["abstract_text"]) <= 10000 and
             type(document["body_text"]) is str and
             0 < len(document["body_text"]) <= 60000 and
             document["normalization"] == NORMALIZATION,
             "CONSTRUCTION_DOCUMENT_TEXT_INVALID")
    paragraphs = document["paragraphs"]
    _require(type(paragraphs) is list and bool(paragraphs),
             "CONSTRUCTION_DOCUMENT_PARAGRAPHS_MISSING")
    expected_parts: list[str] = []
    expected_position = 0
    paragraph_keys = {"section_path", "section_headings", "kind", "ordinal", "text",
                      "start_offset", "end_offset", "span_id"}
    for index, paragraph in enumerate(paragraphs):
        _require(type(paragraph) is dict and set(paragraph) == paragraph_keys,
                 "CONSTRUCTION_PARAGRAPH_FIELDS_INVALID")
        separator = "\n\n" if index else ""
        expected_position += len(separator)
        text = paragraph["text"]
        _require(type(text) is str and bool(text) and
                 paragraph["start_offset"] == expected_position and
                 paragraph["end_offset"] == expected_position + len(text) and
                 document["body_text"][paragraph["start_offset"]:paragraph["end_offset"]] == text,
                 "CONSTRUCTION_PARAGRAPH_OFFSETS_INVALID")
        expected_anchor = "spanv1_" + construction.digest([
            construction.SPAN_VERSION, token, paragraph["section_path"],
            paragraph["ordinal"], construction.sha_text(text)])
        _require(paragraph["span_id"] == expected_anchor,
                 "CONSTRUCTION_PARAGRAPH_ANCHOR_INVALID")
        expected_parts.append(separator + text)
        expected_position += len(text)
    _require("".join(expected_parts) == document["body_text"],
             "CONSTRUCTION_BODY_PARAGRAPH_RECONSTRUCTION_MISMATCH")


def _validate_bundle(bundle: dict[str, Any]) -> tuple[dict[str, Any], bytes, bytes]:
    expected = bundle["expected_identity"]
    handoff = bundle["handoff"]
    source = bundle["source"]
    _require(handoff.get("schema_version") == "ProspectiveAuthoritativeHandoffV1" and
             handoff.get("historical_evidence") is False and
             handoff.get("scientific_result") is False,
             "HANDOFF_BOUNDARY_MISMATCH")
    _require(type(handoff.get("sources")) is list and len(handoff["sources"]) == 1,
             "HANDOFF_SOURCE_COUNT_MISMATCH")
    source_handoff = handoff["sources"][0]
    _require({key: source.get(key) for key in ("source_id", "pmid", "pmcid", "doi")} == expected,
             "SOURCE_IDENTITY_MISMATCH")
    _require(source_handoff.get("source_id") == expected["source_id"] and
             source_handoff.get("request_id") == expected["source_id"] + ":JATS",
             "HANDOFF_SOURCE_IDENTITY_MISMATCH")
    _require(source_handoff.get("source_reference") == bundle["gates"].get("source_reference"),
             "HANDOFF_SOURCE_REFERENCE_MISMATCH")
    _require(source_handoff.get("source_reference") == bundle["source_reference"],
             "HANDOFF_SOURCE_REFERENCE_MISMATCH")
    _require(source_handoff.get("gates") == bundle["gate_reference"],
             "HANDOFF_GATE_REFERENCE_MISMATCH")
    _require(source_handoff.get("capture") == bundle["capture_reference"],
             "HANDOFF_CAPTURE_REFERENCE_MISMATCH")

    raw_ref = source_handoff.get("raw_artifact")
    outputs = source_handoff.get("outputs")
    _require(raw_ref == bundle["raw_jats_reference"], "HANDOFF_RAW_JATS_REFERENCE_MISMATCH")
    _require(type(outputs) is dict and
             outputs.get("normalized_jats") == bundle["normalized_jats_reference"] and
             outputs.get("canonical_body") == bundle["canonical_body_reference"],
             "HANDOFF_OUTPUT_REFERENCE_MISMATCH")
    _require(type(raw_ref) is dict and sha256(bundle["raw_jats"]) == raw_ref.get("sha256") and
             len(bundle["raw_jats"]) == raw_ref.get("byte_count"),
             "RAW_JATS_HASH_MISMATCH")
    _require(type(outputs) is dict and
             sha256(bundle["normalized_jats"]) == outputs.get("normalized_jats", {}).get("sha256") and
             len(bundle["normalized_jats"]) == outputs.get("normalized_jats", {}).get("byte_count"),
             "NORMALIZED_JATS_HASH_MISMATCH")
    _require(sha256(bundle["canonical_body"]) == outputs.get("canonical_body", {}).get("sha256") and
             len(bundle["canonical_body"]) == outputs.get("canonical_body", {}).get("byte_count"),
             "CANONICAL_BODY_HASH_MISMATCH")

    gates = bundle["gates"]
    _require(gates.get("raw_artifact") == raw_ref and gates.get("outputs") == outputs,
             "HANDOFF_GATE_REFERENCE_MISMATCH")
    actual = gates.get("actual")
    _require(type(actual) is dict and actual.get("eligible") is True,
             "JATS_GATE_NOT_ELIGIBLE")
    validator = actual.get("validator_result")
    _require(type(validator) is dict and
             validator.get("identity_state") == "JATS_PRIMARY_IDENTITY_EXACTLY_BOUND" and
             validator.get("source_identity_allows_progression") is True and
             validator.get("expected_identity") == {"pmid": expected["pmid"],
                                                      "pmcid": expected["pmcid"],
                                                      "doi": expected["doi"]},
             "JATS_IDENTITY_GATE_FAILED")
    _require(actual.get("license", {}).get("state") == "CONSTRUCTION_OA_ELIGIBLE",
             "OA_LICENSE_GATE_FAILED")
    _require(actual.get("source_type", {}).get("state") == "SOURCE_TYPE_ELIGIBLE",
             "SOURCE_TYPE_GATE_FAILED")
    _require(actual.get("UpdateOf", {}).get("state") == "CORRECTION_REFERENCE_CLEAR",
             "UPDATEOF_GATE_FAILED")
    _require(actual.get("body_state") == "CANONICAL_BODY_USABLE",
             "CANONICAL_BODY_GATE_FAILED")

    capture = bundle["capture"]
    body = capture.get("body")
    _require(capture.get("failure_occurrence") is None and type(body) is dict and
             body.get("completion_state") == "BODY_COMPLETE" and
             body.get("read_returned_normally") is True and
             body.get("partial_body_artifact_path") is None and
             body.get("partial_body_sha256") is None and
             body.get("complete_body_sha256") == raw_ref["sha256"] and
             capture.get("raw_artifact") == raw_ref,
             "PARTIAL_OR_QUARANTINED_BODY_REJECTED")

    _require(bundle["activation"].get("activated_request_ids") ==
             [expected["source_id"] + ":JATS"], "JATS_ACTIVATION_GATE_MISSING")
    oa_outcomes = bundle["barrier"].get("oa_outcomes")
    _require(type(oa_outcomes) is list and len(oa_outcomes) == 1 and
             oa_outcomes[0].get("request_id") == expected["source_id"] + ":OA" and
             oa_outcomes[0].get("outcome") == "VALID_SUCCESS" and
             oa_outcomes[0].get("eligibility", {}).get("eligible") is True,
             "OA_ACTIVATION_GATE_FAILED")

    terminal = source_handoff.get("terminal")
    _require(type(terminal) is dict, "UNCOMMITTED_TERMINAL_REJECTED")
    matches = [event for event in bundle["journal"]
               if event.get("sequence_number") == terminal.get("journal_sequence_number") and
               event.get("entry_hash") == terminal.get("journal_entry_hash")]
    _require(len(matches) == 1, "UNCOMMITTED_TERMINAL_REJECTED")
    event = matches[0]
    _require(event.get("event_type") == "ATTEMPT_TERMINAL" and
             event.get("logical_request_id") == expected["source_id"] + ":JATS" and
             event.get("event_payload", {}).get("outcome") == "VALID_SUCCESS" and
             event.get("event_payload", {}).get("eligibility", {}).get("eligible") is True and
             event.get("event_payload", {}).get("raw_artifact") == raw_ref and
             handoff.get("journal_tip_sha256") == terminal.get("journal_entry_hash"),
             "UNCOMMITTED_TERMINAL_REJECTED")
    index = bundle["evidence_index"]
    _require(index.get("journal_integrity") == "VERIFIED" and
             index.get("journal_tip_sha256") == handoff.get("journal_tip_sha256") and
             index.get("handoff", {}).get("sha256") == bundle["handoff_sha256"],
             "EVIDENCE_INDEX_BINDING_INVALID")

    identity = identity_policy.validate_jats_primary_identity_v2(
        bundle["raw_jats"], expected_pmid=expected["pmid"],
        expected_pmcid=expected["pmcid"], expected_doi=expected["doi"])
    _require(identity.get("identity_state") == "JATS_PRIMARY_IDENTITY_EXACTLY_BOUND" and
             identity.get("source_identity_allows_progression") is True,
             "JATS_IDENTITY_REVALIDATION_FAILED")
    normalized = ET.tostring(identity_policy.select_primary_article(bundle["raw_jats"]),
                             encoding="utf-8")
    _require(normalized == bundle["normalized_jats"], "NORMALIZED_JATS_REPRODUCTION_MISMATCH")
    license_state = license_policy.construction_oa_v2(expected["pmcid"], True, normalized)
    source_type = construction.source_type_state(source.get("publication_types"), normalized)
    updateof = correction.classify(source.get("publication_types"),
        source.get("correction_relationships"), independent_primary_state=source_type["state"])
    _require(license_state.get("state") == "CONSTRUCTION_OA_ELIGIBLE" and
             source_type.get("state") == "SOURCE_TYPE_ELIGIBLE" and
             updateof.get("state") == "CORRECTION_REFERENCE_CLEAR",
             "SCIENTIFIC_SOURCE_GATE_REVALIDATION_FAILED")
    canonical_body = body_policy.canonical_body(normalized)["body_text"].encode("utf-8")
    _require(canonical_body == bundle["canonical_body"],
             "CANONICAL_BODY_REPRODUCTION_MISMATCH")
    return source_handoff, normalized, canonical_body


def adapt_evidence_bundle(bundle: dict[str, Any], token_authority: dict[str, Any] | None,
                          repository_root: Path) -> dict[str, Any]:
    source_handoff, normalized_jats, canonical_body = _validate_bundle(bundle)
    token = validate_opaque_source_token(token_authority, bundle, repository_root)
    document = construction.build_construction_document(normalized_jats, token)
    validate_construction_document(document, token)
    document_raw = canonical(document)
    return {
        "schema_version": "VerifiedConstructionInputV1",
        "construction_document": document,
        "construction_document_sha256": sha256(document_raw),
        "controller_private_provenance": {
            "pilot_root_sha256": bundle["pilot_root_sha256"],
            "handoff_sha256": bundle["handoff_sha256"],
            "handoff_reference": copy.deepcopy(bundle["handoff_reference"]),
            "source_identity": copy.deepcopy(bundle["expected_identity"]),
            "terminal": copy.deepcopy(source_handoff["terminal"]),
            "source_reference": copy.deepcopy(source_handoff["source_reference"]),
            "capture_reference": copy.deepcopy(source_handoff["capture"]),
            "gate_reference": copy.deepcopy(source_handoff["gates"]),
            "raw_jats_reference": copy.deepcopy(source_handoff["raw_artifact"]),
            "normalized_jats_reference": copy.deepcopy(source_handoff["outputs"]["normalized_jats"]),
            "canonical_body_reference": copy.deepcopy(source_handoff["outputs"]["canonical_body"]),
            "canonical_body_sha256_revalidated": sha256(canonical_body),
            "opaque_source_token": token,
            "opaque_source_token_sha256": token_authority["opaque_source_token_sha256"],
            "opaque_source_token_authority": copy.deepcopy(token_authority["generation"]),
            "evidence_index_sha256": bundle["evidence_index_sha256"],
        },
        "model_visible_public_source_identity_fields": [],
        "builder_or_quality_result": False,
    }


def adapt_verified_handoff(config: AdapterConfig,
                           token_authority: dict[str, Any] | None) -> dict[str, Any]:
    bundle = load_verified_evidence_bundle(config)
    return adapt_evidence_bundle(bundle, token_authority, config.repository_root)


def verify_downstream_deterministic_consumer(envelope: dict[str, Any]) -> dict[str, Any]:
    _require(envelope.get("schema_version") == "VerifiedConstructionInputV1",
             "DOWNSTREAM_ENVELOPE_SCHEMA_INVALID")
    provenance = envelope.get("controller_private_provenance")
    _require(type(provenance) is dict, "DOWNSTREAM_PROVENANCE_MISSING")
    token = provenance.get("opaque_source_token")
    document = envelope.get("construction_document")
    validate_construction_document(document, token)
    _require(envelope.get("construction_document_sha256") == sha256(canonical(document)),
             "DOWNSTREAM_DOCUMENT_HASH_MISMATCH")
    paragraph = document["paragraphs"][0]
    resolved = construction.resolve_candidate_span(
        document, "body", paragraph["start_offset"], paragraph["end_offset"],
        paragraph["text"])
    _require(resolved == paragraph["span_id"], "DOWNSTREAM_SPAN_RESOLUTION_MISMATCH")
    return {
        "status": "PASS",
        "consumer": "resolve_candidate_span",
        "construction_document_sha256": envelope["construction_document_sha256"],
        "canonical_body_sha256": provenance["canonical_body_reference"]["sha256"],
        "normalized_jats_sha256": provenance["normalized_jats_reference"]["sha256"],
        "source_identity_preserved_controller_private": True,
        "resolved_existing_paragraph_anchor": resolved,
        "scientific_candidate_created": False,
    }
