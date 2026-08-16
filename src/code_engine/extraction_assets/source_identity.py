"""Offline, fail-closed scientific source identity contracts.

Publication, repository asset, and extraction provenance are deliberately
separate identities.  Historical identifier values are evidence, never an
instruction to overwrite a locally verified identity.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


IdentityStatus = Literal[
    "exact_verified", "verified_alias", "historical_alias_preserved",
    "identifier_conflict", "publication_asset_mismatch", "ambiguous_identity",
    "insufficient_identity_evidence", "unresolved",
]
Authority = Literal[
    "structured_identifier_exact", "local_xml_metadata", "validated_manifest",
    "source_asset_metadata", "exact_title_identity", "historical_mapping",
    "heuristic_similarity",
]


def stable_identity(kind: str, value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{kind}_{hashlib.sha256(encoded.encode()).hexdigest()[:24]}"


def normalize_identifier(value: Any, kind: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if kind == "doi":
        text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text, flags=re.I)
        return text.casefold().rstrip(". ")
    if kind == "pmcid":
        digits = re.sub(r"^pmc", "", text, flags=re.I)
        return f"PMC{digits}" if digits.isdigit() else text.upper()
    if kind == "pmid":
        return re.sub(r"^pmid:\s*", "", text, flags=re.I)
    return text


def normalize_title(value: Any) -> str | None:
    if not value:
        return None
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split()) or None


class StrictIdentityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IdentifierAuthorityState(StrictIdentityModel):
    identifier_type: Literal["pmid", "pmcid", "doi", "title"]
    value: str
    authority: Authority
    evidence_refs: list[str] = Field(min_length=1)
    current_authority: bool


class CanonicalPublicationIdentityV1(StrictIdentityModel):
    schema_version: Literal["canonical_publication_identity_v1"] = "canonical_publication_identity_v1"
    publication_identity_id: str
    internal_source_ids: list[str]
    pmid: str | None
    pmcid_candidates: list[str]
    doi: str | None
    title_raw: str | None
    title_normalized: str | None
    publication_year: int | None
    journal: str | None
    identifier_authority_states: list[IdentifierAuthorityState]
    identity_status: IdentityStatus
    provenance_refs: list[str]
    historical_aliases: list[dict[str, Any]]
    conflicting_aliases: list[dict[str, Any]]
    identity_sha256: str


class SourceAssetIdentityV1(StrictIdentityModel):
    schema_version: Literal["source_asset_identity_v1"] = "source_asset_identity_v1"
    source_asset_identity_id: str
    publication_identity_id: str | None
    asset_type: Literal["local_xml", "retrieval_record", "abstract_record", "cached_source"]
    pmcid: str | None
    local_path: str | None
    asset_sha256: str | None
    identity_status: IdentityStatus
    authority: Authority
    provenance_refs: list[str] = Field(min_length=1)


class ExtractionSourceIdentityV1(StrictIdentityModel):
    schema_version: Literal["extraction_source_identity_v1"] = "extraction_source_identity_v1"
    extraction_source_identity_id: str
    source_asset_identity_id: str
    extraction_object_id: str
    section: str | None = None
    block_id: str | None = None
    span_ids: list[str] = Field(default_factory=list)
    extraction_run_ref: str


class SourceIdentityReconciliationRevisionV1(StrictIdentityModel):
    schema_version: Literal["source_identity_reconciliation_revision_v1"] = "source_identity_reconciliation_revision_v1"
    revision_id: str
    historical_identity: dict[str, Any]
    reconciled_identity: dict[str, Any]
    status: Literal["historical_alias_non_authoritative", "verified_alias", "unresolved"]
    reason: str
    evidence_refs: list[str] = Field(min_length=1)
    rule_identity: str
    supersedes_relation: Literal["sidecar_only_no_historical_mutation"] = "sidecar_only_no_historical_mutation"


class ProvenanceClosureFactsV1(StrictIdentityModel):
    publication_identity_closed: bool
    source_asset_identity_closed: bool
    exact_span_provenance: bool
    entity_compatible: bool
    experiment_scope_compatible: bool
    measurement_result_compatible: bool
    unresolved_competing_experiment: bool = False


BridgeGateStatus = Literal[
    "bridge_candidate_valid", "blocked_publication_identity",
    "blocked_source_asset_identity", "blocked_provenance", "blocked_entity_identity",
    "blocked_experiment_ambiguity", "blocked_measurement_result_semantics",
    "manual_review_required",
]


def bridge_candidate_gate(facts: ProvenanceClosureFactsV1) -> BridgeGateStatus:
    if not facts.publication_identity_closed:
        return "blocked_publication_identity"
    if not facts.source_asset_identity_closed:
        return "blocked_source_asset_identity"
    if not facts.exact_span_provenance:
        return "manual_review_required"
    if not facts.entity_compatible:
        return "blocked_entity_identity"
    if facts.unresolved_competing_experiment or not facts.experiment_scope_compatible:
        return "blocked_experiment_ambiguity"
    if not facts.measurement_result_compatible:
        return "blocked_measurement_result_semantics"
    return "bridge_candidate_valid"


def identifier_collision_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return exact-identifier collisions; title similarity never authorizes a merge."""
    pmid_to_doi: dict[str, set[str]] = defaultdict(set)
    doi_to_pmid: dict[str, set[str]] = defaultdict(set)
    pmcid_to_pmid: dict[str, set[str]] = defaultdict(set)
    internal_to_publication: dict[str, set[str]] = defaultdict(set)
    for record in records:
        pmid = normalize_identifier(record.get("pmid"), "pmid")
        pmcid = normalize_identifier(record.get("pmcid"), "pmcid")
        doi = normalize_identifier(record.get("doi"), "doi")
        internal = record.get("internal_source_id")
        if pmid and doi:
            pmid_to_doi[pmid].add(doi)
            doi_to_pmid[doi].add(pmid)
        if pmcid and pmid:
            pmcid_to_pmid[pmcid].add(pmid)
        if internal:
            signature = f"pmid:{pmid}" if pmid else (f"doi:{doi}" if doi else "")
            if signature:
                internal_to_publication[str(internal)].add(signature)
    output = []
    checks = (
        ("pmid", pmid_to_doi, "doi"),
        ("doi", doi_to_pmid, "pmid"),
        ("pmcid", pmcid_to_pmid, "pmid"),
        ("internal_source_id", internal_to_publication, "publication"),
    )
    for kind, values, incompatible_kind in checks:
        for value, incompatible_values in values.items():
            if len(incompatible_values) > 1:
                output.append({
                    "collision_type": f"{kind}_multiple_incompatible_{incompatible_kind}",
                    "identifier_type": kind, "identifier_value": value,
                    "incompatible_values": sorted(incompatible_values),
                    "status": "identifier_conflict", "resolution_status": "fail_closed",
                })
    return sorted(output, key=lambda x: (x["identifier_type"], x["identifier_value"]))
