"""Curated omics sign validator.

This validator uses the repository's small curated/demo registry. It is not a
full LINCS validator and deliberately reports unresolved coverage when the
registry lacks an anchor for the hypothesis target.
"""

from __future__ import annotations

import json
import os
import hashlib
from collections.abc import Iterator
from typing import Dict

from .base import AbstractValidator
from .skeleton import ExternalIndexValidator
from code_engine.schemas.validation import ExternalEvidenceRecord, ValidationExecutionContext, ValidationQueryPlan, ValidationQuestion, ValidationResult


UNRESPONSIVE_Z_THRESHOLD = 0.50
MIN_PEDIGREE_VOTE_THRESHOLD = 0.60


class CuratedOmicsValidator(ExternalIndexValidator):
    name = "CuratedOmicsValidator"
    supported_domains = ("neuropharmacology",)
    supported_relation_types = ("drug_gene_expression", "pathway_expression")
    supported_entity_types = ("compound", "gene", "protein", "pathway")
    required_resources = ("curated_omics_registry",)
    supported_anchor_types = ("triple_anchor", "gene_set_anchor", "hypothesis_anchor", "conflict_anchor")
    supported_validation_intents = ("expression_direction_check",)
    supports_local_index = True
    index_name = "curated_omics"
    source_database = "curated_omics_registry"
    evidence_type = "curated_expression_direction"
    default_signal_type = "expression_support"
    interpretation_limits = ("Curated/demo omics index; not full LINCS validation.", "External evidence is not proof.")

    def __init__(
        self,
        lincs_index_path: str = "configs/validators/curated_omics_registry.json",
        cell_mask_path: str = "configs/validators/cell_ontology_pedigree.json",
    ):
        self.lincs_index_path = lincs_index_path
        self.cell_mask_path = cell_mask_path
        self.registry = self._load_registry()
        self.pedigree_mask = self._load_cell_pedigree_mask()

    def _load_registry(self) -> Dict[str, dict]:
        if not os.path.exists(self.lincs_index_path):
            return {}
        with open(self.lincs_index_path, "r", encoding="utf-8") as handle:
            return json.load(handle).get("perturbation_registry", {})

    def _load_cell_pedigree_mask(self) -> Dict[str, list]:
        if not os.path.exists(self.cell_mask_path):
            return {
                "cns_contexts": ["PRIMARY_NEURON", "CORTICAL_NEURON", "CNS", "BRAIN", "HIPPOCAMPUS"],
                "cns_cells": ["NEURON_CL", "PC12", "SKNMC", "SHSY5Y"],
                "peripheral_cells": ["A549", "MCF7", "PC3", "HEPG2"],
            }
        with open(self.cell_mask_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)["cell_ontology_pedigree_mask"]
        return {
            "cns_contexts": data["CNS_NERVOUS_SYSTEM_CELLS"]["target_contexts"],
            "cns_cells": data["CNS_NERVOUS_SYSTEM_CELLS"]["lincs_high_weight_cells"],
            "peripheral_cells": data["PERIPHERAL_OUT-OF-DOMAIN_SYSTEMS"]["forbidden_dilv_cells"],
        }

    def _target_entity(self, hypothesis: dict) -> str:
        tokens = str(hypothesis.get("seed_pair", "")).split(" -> ")
        return tokens[1].strip().upper() if len(tokens) >= 2 else ""

    def can_validate(self, hypothesis: dict) -> bool:
        if isinstance(hypothesis, ValidationQuestion):
            return AbstractValidator.can_validate(self, hypothesis)
        return self._target_entity(hypothesis) in self.registry

    def stream_evidence(self, query_plan: ValidationQueryPlan, context: ValidationExecutionContext) -> Iterator[ExternalEvidenceRecord]:
        terms = {
            str(value).upper()
            for entity in query_plan.query_entities
            for value in (entity.get("canonical_name"), entity.get("name"), entity.get("canonical_id"))
            if value
        }
        emitted = 0
        for target, profile in self.registry.items():
            if target.upper() not in terms and not any(target.upper() in term for term in terms):
                continue
            for cell, metrics in profile.get("cell_lines", {}).items():
                z_score = float(metrics.get("z_score", 0.0))
                direction = "increase" if z_score > 0 else "decrease" if z_score < 0 else "no_effect"
                stable = f"{query_plan.query_plan_id}|{target}|{cell}"
                yield ExternalEvidenceRecord(
                    evidence_id=hashlib.sha256(stable.encode()).hexdigest()[:16],
                    validator_name=self.name, source_database=self.source_database,
                    query_plan_id=query_plan.query_plan_id, anchor_id=query_plan.anchor_id,
                    evidence_type=self.evidence_type,
                    target_entity={"name": target, "registry_anchor_gene": self._resolve_anchor_gene(profile)},
                    context={"cell_line": cell, "expected_direction": query_plan.query_context.get("expected_direction")},
                    record_id=f"{target}:{cell}", direction=direction, score=abs(z_score), effect_size=z_score,
                    interpretation_limits=list(self.interpretation_limits),
                )
                emitted += 1
                if emitted >= query_plan.max_records:
                    return

    def _resolve_anchor_gene(self, entity_profile: dict) -> str:
        """Resolve anchor gene using current fields before legacy target_gene."""

        return (
            entity_profile.get("registry_anchor_gene")
            or entity_profile.get("omics_anchor_gene")
            or entity_profile.get("target_gene")
            or "UNKNOWN"
        )

    def validate(self, hypothesis: dict) -> dict:
        if isinstance(hypothesis, ValidationQuestion):
            if not self.registry:
                return ValidationResult(
                    hypothesis_id=hypothesis.hypothesis_id,
                    validator_name=self.name,
                    domain_id=hypothesis.domain_id,
                    validator_profile_id=hypothesis.validator_profile_id,
                    validation_status="external_index_not_configured",
                    coverage_status="none",
                    limitations=["Curated omics registry is not configured."],
                )
            return ValidationResult(
                hypothesis_id=hypothesis.hypothesis_id,
                validator_name=self.name,
                domain_id=hypothesis.domain_id,
                validator_profile_id=hypothesis.validator_profile_id,
                validation_status="no_coverage",
                coverage_status="curated_registry",
                limitations=["Question-level curated lookup requires a mapped registry anchor."],
            )
        h_id = hypothesis.get("hypothesis_id", "UNKNOWN")
        target_entity = self._target_entity(hypothesis)
        if target_entity not in self.registry:
            return {
                "hypothesis_id": h_id,
                "validator": self.name,
                "status": "Unresolved_No_Coverage",
                "coverage": "none",
                "score": None,
                "evidence": [],
                "limitations": [f"No curated omics registry anchor for target entity: {target_entity or 'UNKNOWN'}."],
            }

        expected_relation_sign = 1
        for trace in hypothesis.get("whitebox_traceability", []):
            if "relation_sign" in trace:
                expected_relation_sign = trace["relation_sign"]
                break

        entity_profile = self.registry[target_entity]
        cell_lines_data = entity_profile.get("cell_lines", {})
        is_cns_target_chain = False
        for trace in hypothesis.get("whitebox_traceability", []):
            snapshot_str = json.dumps(trace.get("context_snapshot", {})).upper()
            if any(ctx in snapshot_str for ctx in self.pedigree_mask["cns_contexts"]):
                is_cns_target_chain = True
                break

        weighted_votes = []
        total_weights = []
        evidence = []
        sign_mismatch_in_high_weight_cells = False
        for cell_name, metrics in cell_lines_data.items():
            z_val = float(metrics["z_score"])
            abs_z = abs(z_val)
            cell_weight = 1.0
            if is_cns_target_chain:
                if cell_name in self.pedigree_mask["cns_cells"]:
                    cell_weight = 2.5
                elif cell_name in self.pedigree_mask["peripheral_cells"]:
                    cell_weight = 0.2
            total_weights.append(cell_weight)

            vote = 0.0
            status = "unresponsive"
            if abs_z > UNRESPONSIVE_Z_THRESHOLD:
                lincs_sign = 1 if z_val > 0 else -1
                if lincs_sign == expected_relation_sign:
                    vote = 1.0 * cell_weight
                    status = "sign_consistent"
                else:
                    status = "sign_inconsistent"
                    if cell_weight > 1.0:
                        sign_mismatch_in_high_weight_cells = True
            weighted_votes.append(vote)
            evidence.append({"cell_line": cell_name, "z_score": z_val, "cell_weight": cell_weight, "status": status})

        final_score = sum(weighted_votes) / sum(total_weights) if total_weights else 0.0
        limitations = ["Curated/demo omics index; not full LINCS validation."]
        anchor_gene = self._resolve_anchor_gene(entity_profile)
        base = {
            "hypothesis_id": h_id,
            "validator": self.name,
            "coverage": "curated_registry",
            "score": round(final_score, 4),
            "evidence": evidence,
            "limitations": limitations,
            "registry_anchor_gene": anchor_gene,
            "omics_anchor_gene": entity_profile.get("omics_anchor_gene") or anchor_gene,
            "anchor_gene": anchor_gene,
        }
        if sign_mismatch_in_high_weight_cells or final_score < MIN_PEDIGREE_VOTE_THRESHOLD:
            return {**base, "status": "Sign_Inconsistent_Under_Curated_Index"}
        return {**base, "status": "Sign_Consistent_Under_Curated_Index"}
