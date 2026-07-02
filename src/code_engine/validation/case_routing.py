"""Configuration-driven case profiling and external-validator selection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel


class CaseDomainProfile(CODEBaseModel):
    case_id: str
    query: str
    case_type: str
    disease_areas: list[str] = Field(default_factory=list)
    mechanism_areas: list[str] = Field(default_factory=list)
    entity_types: list[str] = Field(default_factory=list)
    intervention_types: list[str] = Field(default_factory=list)
    validation_needs: list[str] = Field(default_factory=list)
    expected_validators: list[str] = Field(default_factory=list)
    optional_validators: list[str] = Field(default_factory=list)
    excluded_validators: list[str] = Field(default_factory=list)
    profile_version: str = "1.0"

    @classmethod
    def from_domain_profile(cls, domain_profile: dict[str, Any], *, case_id: str, query: str) -> "CaseDomainProfile":
        domain_id = str(domain_profile.get("domain_id") or "general_biomedical")
        needs_by_domain = {
            "drug_target_binding": ["drug_target_annotation"],
            "pathway_biology": ["pathway_membership"],
            "protein_interaction": ["protein_interaction"],
            "clinical_outcome": ["post_cutoff_literature"],
            "neuropharmacology": ["expression_dataset"],
        }
        return cls(
            case_id=case_id, query=query, case_type=domain_id,
            entity_types=list(domain_profile.get("key_entity_types") or []),
            validation_needs=needs_by_domain.get(domain_id, []),
            expected_validators=list(domain_profile.get("preferred_validators") or []),
            optional_validators=list(domain_profile.get("fallback_validators") or []),
        )


def load_case_domain_profile(path: str | Path) -> CaseDomainProfile:
    return CaseDomainProfile.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _matches(profile: CaseDomainProfile, when: dict[str, list[str]]) -> bool:
    for field, required in when.items():
        actual = set(getattr(profile, field, []))
        if not set(required).issubset(actual):
            return False
    return True


def route_case_validators(
    profile: CaseDomainProfile, *, external_data_root: str | Path = "data/external",
    lincs_dataset: str = "GSE70138",
    registry_path: str | Path = "configs/validation/validator_registry.json",
    mapping_path: str | Path = "configs/validation/domain_to_validator_map.json",
    manual_cli_validators: list[str] | None = None,
) -> dict[str, Any]:
    registry = {item["validator_id"]: item for item in _load(registry_path)["validators"]}
    matched: dict[str, list[str]] = {}
    required: list[str] = []
    optional: list[str] = []
    for rule in _load(mapping_path)["rules"]:
        if not _matches(profile, rule.get("when", {})):
            continue
        for kind, destination in (("required", required), ("optional", optional)):
            for validator_id in rule.get("recommend", {}).get(kind, []):
                if validator_id not in destination:
                    destination.append(validator_id)
                matched.setdefault(validator_id, []).append(rule["rule_id"])
    for validator_id in profile.expected_validators:
        if validator_id not in required:
            required.append(validator_id)
        matched.setdefault(validator_id, []).append("case_profile_expected_validator")
    for validator_id in profile.optional_validators:
        if validator_id not in optional and validator_id not in required:
            optional.append(validator_id)
        matched.setdefault(validator_id, []).append("case_profile_optional_validator")

    excluded = set(profile.excluded_validators)
    manual = list(dict.fromkeys(manual_cli_validators or []))
    candidates = list(dict.fromkeys(required + optional + manual))
    decisions = []
    selected = []
    unavailable = []
    for validator_id in candidates:
        spec = registry.get(validator_id)
        if spec is None:
            availability = "not_present"
        else:
            availability = spec["status"]
        resource_available = True
        if validator_id == "lincs_l1000":
            root = Path(external_data_root) / "lincs_l1000" / "index" / lincs_dataset
            perturbagen = profile.query.split()[0] if profile.query.split() else ""
            resource_available = bool(perturbagen) and (root / f"{perturbagen}_index_summary.json").is_file() and (root / f"{perturbagen}_top_genes.jsonl").is_file()
            if availability == "runnable" and not resource_available:
                availability = "not_configured"
        if validator_id in excluded:
            decision = "excluded_by_case_profile"
            reason = "validator is explicitly excluded by the case profile"
        elif availability == "runnable" and resource_available:
            decision = "selected_for_execution"
            selected.append(validator_id)
            reason = "case tags and validation needs matched; required local resources are available"
        else:
            decision = "recommended_but_unavailable"
            unavailable.append(validator_id)
            reason = (spec or {}).get("unavailable_reason", "validator is not operationally configured")
        decisions.append({
            "validator_id": validator_id, "decision": decision,
            "matched_rules": list(dict.fromkeys(matched.get(validator_id, []) + (["manual_cli_override"] if validator_id in manual else []))),
            "availability": availability, "reason": reason,
        })
    return {
        "selection_mode": "domain_aware_router",
        "selected_validators": selected,
        "recommended_but_unavailable": unavailable,
        "manual_cli_overrides": manual,
        "deduplicated": any(item in selected and item in manual for item in manual),
        "decisions": decisions,
    }


__all__ = ["CaseDomainProfile", "load_case_domain_profile", "route_case_validators"]
