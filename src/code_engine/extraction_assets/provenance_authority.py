"""Authority-aware, offline provenance closure and collision contracts.

An internal edge to a publication object is deliberately weaker than external
publication verification.  The helpers in this module classify already-built
local identities; they never resolve identifiers or contact a provider.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ClosureAuthority = Literal[
    "closed_exact_verified",
    "closed_verified_alias",
    "closed_historical_alias",
    "closed_internal_publication_only",
    "closed_to_unresolved_external_identity",
    "closed_to_identifier_conflict",
    "closure_missing",
]
IdentifierState = Literal[
    "exact_verified",
    "verified_alias",
    "historical_alias",
    "internal_only",
    "unresolved",
    "conflict",
    "missing",
]
CollisionClass = Literal[
    "benign_duplicate_internal_mapping",
    "multiple_source_assets_same_publication",
    "historical_alias_collision",
    "same_publication_multiple_internal_ids",
    "cross_publication_identifier_conflict",
    "asset_level_identifier_collision",
    "unresolved_collision",
]


def stable(kind: str, payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{kind}_{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PublicationClosureAuthorityV1(StrictModel):
    schema_version: Literal["publication_closure_authority_v1"] = "publication_closure_authority_v1"
    object_id: str
    object_type: Literal["claim", "observation"]
    publication_identity_id: str | None
    closure_status: Literal["internal_parent_closed", "closure_missing"]
    closure_authority: ClosureAuthority
    pmid_state: IdentifierState
    pmcid_state: IdentifierState
    doi_state: IdentifierState
    publication_identity_status: str | None
    source_asset_status: str
    provenance_refs: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def closure_and_authority_agree(self):
        missing = self.publication_identity_id is None
        if missing != (self.closure_status == "closure_missing"):
            raise ValueError("publication_identity_id_and_closure_status_disagree")
        if missing != (self.closure_authority == "closure_missing"):
            raise ValueError("publication_identity_id_and_closure_authority_disagree")
        return self


class IdentifierCollisionClassificationV1(StrictModel):
    schema_version: Literal["identifier_collision_classification_v1"] = "identifier_collision_classification_v1"
    collision_id: str
    identifier_type: Literal["pmid", "pmcid", "doi", "internal_source_id"]
    identifier_value: str
    incompatible_values: list[str] = Field(min_length=2)
    primary_classification: CollisionClass
    secondary_labels: list[CollisionClass] = Field(default_factory=list)
    authority_evidence: list[dict[str, Any]] = Field(min_length=1)
    publication_identity_ids: list[str] = Field(default_factory=list)
    source_asset_identity_ids: list[str] = Field(default_factory=list)
    resolution_status: Literal["benign", "fail_closed"]
    title_only_merge_forbidden: bool = True

    @model_validator(mode="after")
    def conflicts_fail_closed(self):
        if self.primary_classification in {
            "cross_publication_identifier_conflict", "unresolved_collision"
        } and self.resolution_status != "fail_closed":
            raise ValueError("unresolved_or_true_collision_must_fail_closed")
        return self


def closure_authority_for(
    *, publication_identity_closed: bool, publication_identity_status: str | None,
    has_external_identifier: bool,
) -> ClosureAuthority:
    """Separate internal graph closure from external identity authority."""
    if not publication_identity_closed:
        return "closure_missing"
    if publication_identity_status == "exact_verified":
        return "closed_exact_verified"
    if publication_identity_status == "verified_alias":
        return "closed_verified_alias"
    if publication_identity_status == "historical_alias_preserved":
        return "closed_historical_alias"
    if publication_identity_status in {
        "identifier_conflict", "publication_asset_mismatch", "ambiguous_identity"
    }:
        return "closed_to_identifier_conflict"
    if not has_external_identifier:
        return "closed_internal_publication_only"
    return "closed_to_unresolved_external_identity"


def identifier_state_for(
    *, value_present: bool, publication_identity_status: str | None,
    current_authority: bool = False,
) -> IdentifierState:
    if not value_present:
        return "missing"
    if publication_identity_status == "exact_verified" and current_authority:
        return "exact_verified"
    if publication_identity_status == "verified_alias":
        return "verified_alias"
    if publication_identity_status == "historical_alias_preserved":
        return "historical_alias"
    if publication_identity_status in {
        "identifier_conflict", "publication_asset_mismatch", "ambiguous_identity"
    }:
        return "conflict"
    return "unresolved"


def classify_collision(
    *, identifier_type: Literal["pmid", "pmcid", "doi", "internal_source_id"],
    identifier_value: str, incompatible_values: list[str],
    evidence_rows: list[dict[str, Any]], historical_revision_refs: list[str] | None = None,
    publication_identity_ids: list[str] | None = None,
    source_asset_identity_ids: list[str] | None = None,
) -> IdentifierCollisionClassificationV1:
    """Classify an exact-identifier collision from strong local evidence.

    Exact title equality may corroborate other evidence but can never authorize
    a benign classification by itself.
    """
    revisions = sorted(set(historical_revision_refs or []))
    pub_ids = sorted(set(publication_identity_ids or []))
    asset_ids = sorted(set(source_asset_identity_ids or []))
    internal_ids = sorted({str(x["internal_source_id"]) for x in evidence_rows if x.get("internal_source_id")})
    asset_hashes = sorted({str(x["asset_sha256"]) for x in evidence_rows if x.get("asset_sha256")})
    local_xml = [x for x in evidence_rows if x.get("record_kind") == "local_xml_metadata"]
    titles = sorted({str(x["title_normalized"]) for x in evidence_rows if x.get("title_normalized")})
    years = sorted({str(x["publication_year"]) for x in evidence_rows if x.get("publication_year")})

    authority_evidence: list[dict[str, Any]] = []
    for row in local_xml:
        authority_evidence.append({
            "authority": "local_xml_metadata", "source_ref": row.get("source_path"),
            "pmid": row.get("pmid"), "pmcid": row.get("pmcid"), "doi": row.get("doi"),
            "title_normalized": row.get("title_normalized"), "publication_year": row.get("publication_year"),
        })
    for ref in revisions:
        authority_evidence.append({"authority": "historical_alias_revision", "source_ref": ref})
    if not authority_evidence:
        authority_evidence.append({
            "authority": "local_metadata_inventory", "source_ref": evidence_rows[0].get("source_path", "local_inventory"),
            "distinct_title_count": len(titles), "distinct_year_count": len(years),
        })

    secondary: list[CollisionClass] = []
    if len(internal_ids) > 1:
        secondary.append("same_publication_multiple_internal_ids")
    if len(asset_hashes) > 1:
        secondary.append("multiple_source_assets_same_publication")
    if identifier_type == "pmcid" and (len(asset_hashes) > 1 or len(internal_ids) > 1):
        secondary.append("asset_level_identifier_collision")

    # A versioned revision grounded in local XML is positive evidence that the
    # colliding historical value is non-authoritative.
    if revisions:
        primary: CollisionClass = "historical_alias_collision"
        resolution = "benign"
    # Two incompatible publication descriptions sharing an identifier are a
    # true conflict even when the year happens to agree.
    elif len(titles) > 1 or len(years) > 1:
        primary = "cross_publication_identifier_conflict"
        resolution = "fail_closed"
    elif len(pub_ids) == 1 and len(asset_hashes) > 1:
        primary = "multiple_source_assets_same_publication"
        resolution = "benign"
    elif len(pub_ids) == 1 and len(internal_ids) > 1 and local_xml:
        primary = "benign_duplicate_internal_mapping"
        resolution = "benign"
    else:
        primary = "unresolved_collision"
        resolution = "fail_closed"

    payload = {
        "identifier_type": identifier_type, "identifier_value": identifier_value,
        "incompatible_values": sorted(set(map(str, incompatible_values))),
        "primary_classification": primary, "secondary_labels": sorted(set(secondary)),
        "authority_evidence": authority_evidence, "publication_identity_ids": pub_ids,
        "source_asset_identity_ids": asset_ids, "resolution_status": resolution,
        "title_only_merge_forbidden": True,
    }
    payload["collision_id"] = stable("identifier_collision", {
        "identifier_type": identifier_type, "identifier_value": identifier_value,
        "incompatible_values": payload["incompatible_values"],
    })
    return IdentifierCollisionClassificationV1.model_validate(payload)


def is_external_verified(authority: ClosureAuthority) -> bool:
    return authority in {"closed_exact_verified", "closed_verified_alias"}

