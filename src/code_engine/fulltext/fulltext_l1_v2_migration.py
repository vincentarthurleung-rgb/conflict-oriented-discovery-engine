"""Fail-closed compatibility boundary for paid historical Fulltext L1 v2 JSON."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from code_engine.schemas.fulltext_observation import FulltextL1V2Response


SCHEMA_MIGRATION_VERSION = "fulltext_l1_v2_historical_fields_v2"
OBSERVATION_ID_VERSION = "fulltext_l1_v2_observation_id_sha256_v1"


class HistoricalMigrationError(ValueError):
    """The old response cannot be transformed without guessing or data loss."""


@dataclass(frozen=True)
class TrustedBlockContext:
    run_id: str
    block_id: str
    parent_block_id: str | None
    text: str
    source_block_hash: str
    source_document_id: str
    paper_id: str
    pmid: str | None
    pmcid: str | None
    fulltext_source_hash: str
    source_artifact: str


FIELD_MAPPINGS: tuple[tuple[tuple[str, ...], tuple[str, ...], str], ...] = (
    (("provenance", "experiment_id"), ("experiment", "experiment_id"), "exact_field_relocation"),
    (("provenance", "evidence_family_id"), ("experiment", "evidence_family_id"), "exact_field_relocation"),
    (("provenance", "section_title"), ("provenance", "section"), "exact_field_rename"),
    (("provenance", "source_location"), ("provenance", "section"), "exact_field_rename"),
    (("provenance", "figure"), ("provenance", "figure_ids"), "scalar_reference_to_list"),
    (("provenance", "figure_or_table"), ("provenance", "figure_ids"), "scalar_reference_to_list"),
    (("experiment", "description"), ("experiment", "experimental_design"), "exact_field_rename"),
    (("experiment", "model"), ("experiment", "model_system"), "exact_field_rename"),
    (("experiment", "model_organism"), ("experiment", "species"), "exact_field_rename"),
    (("experiment", "experimental_system"), ("experiment", "model_system"), "exact_field_rename"),
    (("intervention", "type"), ("intervention", "intervention_type"), "controlled_intervention_type_rename"),
    (("intervention", "target"), ("intervention", "intervention_target_mention"), "exact_field_rename"),
    (("measurement", "dimension"), ("measurement", "measurement_dimension"), "exact_field_rename"),
    (("measurement", "entity"), ("measurement", "measured_entity_mention"), "exact_field_rename"),
    (("observation", "magnitude"), ("observation", "effect_size_or_magnitude"), "exact_field_rename"),
)

INTERVENTION_TYPE_VALUES = {
    "genetic knockout": "knockout",
    "knockout": "knockout",
    "knockdown": "knockdown",
    "silencing": "silencing",
    "inhibition": "inhibition",
    "depletion": "depletion",
    "mutation": "mutation",
    "overexpression": "overexpression",
    "activation": "activation",
    "agonism": "agonism",
    "drug treatment": "drug_treatment",
    "drug_treatment": "drug_treatment",
    "rescue": "rescue",
    "re-expression": "re_expression",
    "re_expression": "re_expression",
    "combination treatment": "combination_treatment",
    "combination_treatment": "combination_treatment",
    "observational no intervention": "observational_no_intervention",
    "observational_no_intervention": "observational_no_intervention",
    "unknown": "unknown",
    "none": "observational_no_intervention",
    "genetic_knockout": "knockout", "genetic deletion": "knockout",
    "genetic_deletion": "knockout", "genetic double knockout": "knockout",
    "gene knockout": "knockout", "genetic_knockdown": "knockdown",
    "sirna knockdown": "knockdown", "sirna_knockdown": "knockdown",
    "gene_knockdown": "knockdown", "sirna transfection": "knockdown",
    "pharmacological_inhibition": "inhibition",
    "adenoviral expression": "overexpression",
    "genetic manipulation (overexpression and knockdown)": "combination_treatment",
    "genetic_modification": "unknown", "genetic_perturbation": "unknown",
    "genetic_manipulation": "unknown", "condition": "unknown", "treatment": "unknown",
    "hypoxia": "unknown", "hypoxia_exposure": "unknown", "tissue_comparison": "unknown",
    "chemical": "unknown",
}

# Only values whose complete semantic content is preserved by observed_result.
DIRECTION_TO_OBSERVED_RESULT = {
    "increased": "increased", "decreased": "decreased", "unchanged": "unchanged",
    "no change": "no change", "higher": "higher", "lower": "lower",
    "upregulated": "upregulated", "downregulated": "downregulated",
    "increase": "increase", "down": "down", "suppressed": "suppressed",
    "no significant change": "no significant change", "no_change": "no_change",
    "no significant difference": "no significant difference", "worse survival": "worse survival",
    "increase in luad relative to normal": "increase in LUAD relative to normal",
    "sa treatment reduced migration": "SA treatment reduced migration",
    "unchanged_or_moderately_altered": "unchanged_or_moderately_altered",
    "marginally reduced": "marginally reduced",
}


def _sha256(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _get(root: dict[str, Any], path: tuple[str, ...]) -> tuple[bool, Any]:
    current: Any = root
    for part in path[:-1]:
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return (isinstance(current, dict) and path[-1] in current,
            current.get(path[-1]) if isinstance(current, dict) else None)


def _set(root: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = root
    for part in path[:-1]:
        child = current.setdefault(part, {})
        if not isinstance(child, dict):
            raise HistoricalMigrationError(f"destination parent is not an object: {'.'.join(path[:-1])}")
        current = child
    current[path[-1]] = value


def _delete(root: dict[str, Any], path: tuple[str, ...]) -> None:
    current: Any = root
    for part in path[:-1]:
        if not isinstance(current, dict):
            return
        current = current.get(part)
    if isinstance(current, dict):
        current.pop(path[-1], None)


def _audit_base(context: TrustedBlockContext, raw_response_path: str, original: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "run_id": context.run_id, "paper_id": context.paper_id, "pmid": context.pmid,
        "pmcid": context.pmcid, "block_id": context.block_id,
        "observation_index": index, "raw_response_path": raw_response_path,
        "original_schema_version": original.get("schema_version"),
        "migration_version": SCHEMA_MIGRATION_VERSION,
    }


def _move(row: dict[str, Any], source: tuple[str, ...], destination: tuple[str, ...], rule: str,
          audit: list[dict[str, Any]], base: dict[str, Any]) -> None:
    exists, value = _get(row, source)
    if not exists:
        return
    if source == ("intervention", "type"):
        mapped = INTERVENTION_TYPE_VALUES.get(str(value).strip().casefold())
        if mapped is None:
            raise HistoricalMigrationError(f"intervention.type value is not whitelisted: {value!r}")
        value = mapped
    if rule == "scalar_reference_to_list" and not isinstance(value, list):
        value = [] if value is None else [str(value)]
    destination_exists, destination_value = _get(row, destination)
    if destination_exists and destination_value != value:
        raise HistoricalMigrationError(
            f"conflicting source/destination fields: {'.'.join(source)} -> {'.'.join(destination)}")
    _set(row, destination, value)
    _delete(row, source)
    audit.append({**base, "original_field_path": ".".join(source), "original_value": value,
                  "destination_field_path": ".".join(destination), "migrated_value": value,
                  "migration_rule": rule, "value_source": "historical_raw_response"})


def locate_evidence_span(text: str, block_text: str, *, section: str | None = None) -> dict[str, Any]:
    """Locate a verbatim span; ambiguity is never resolved semantically."""
    if not isinstance(text, str) or not text:
        raise HistoricalMigrationError("evidence_span_missing")
    starts: list[int] = []
    offset = 0
    while True:
        found = block_text.find(text, offset)
        if found < 0:
            break
        starts.append(found)
        offset = found + 1
    if not starts:
        raise HistoricalMigrationError("evidence_span_missing")
    if len(starts) > 1:
        # A section label can disambiguate only when it defines a literal block
        # region and exactly one occurrence is inside that region.
        marker = str(section or "").strip()
        if marker:
            marker_at = block_text.find(marker)
            candidates = [x for x in starts if marker_at >= 0 and x >= marker_at]
            if len(candidates) == 1:
                starts = candidates
        if len(starts) != 1:
            raise HistoricalMigrationError("evidence_span_ambiguous")
    start = starts[0]
    return {"text": text, "span_type": "observation", "section": section,
            "char_start": start, "char_end": start + len(text)}


def deterministic_observation_id(row: dict[str, Any], context: TrustedBlockContext,
                                 span: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    inputs = {
        "version": OBSERVATION_ID_VERSION,
        "source_document_id": context.source_document_id,
        "parent_block_id": context.parent_block_id,
        "child_block_id": context.block_id,
        "experiment_identifier": (row.get("experiment") or {}).get("experiment_id"),
        "species": (row.get("experiment") or {}).get("species"),
        "intervention_raw_fields": row.get("intervention"),
        "comparison_raw_fields": {
            "experiment_comparison_arm": (row.get("experiment") or {}).get("comparison_arm"),
            "experiment_control_arm": (row.get("experiment") or {}).get("control_arm"),
            "observation_comparison_relation": (row.get("observation") or {}).get("comparison_relation"),
        },
        "measurement_raw_fields": row.get("measurement"),
        "observed_result": (row.get("observation") or {}).get("observed_result"),
        "normalized_evidence_span_hash": _sha256({k: span.get(k) for k in ("text", "char_start", "char_end")}),
    }
    digest = _sha256(inputs)
    return f"ftl1v2_{digest[:24]}", {"inputs": inputs, "inputs_hash": digest,
                                      "algorithm_version": OBSERVATION_ID_VERSION}


def migrate_historical_response(payload: dict[str, Any], *, context: TrustedBlockContext,
                                raw_response_path: str, original_prompt_version: str | None,
                                original_prompt_hash: str | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply only explicit old-path mappings, then validate the strict schema."""
    if not isinstance(payload, dict) or not isinstance(payload.get("experimental_observations"), list):
        raise HistoricalMigrationError("response does not contain experimental_observations list")
    migrated = deepcopy(payload)
    migrated["schema_version"] = "fulltext_l1_experimental_observation_schema_v2"
    audit: list[dict[str, Any]] = []
    for index, row in enumerate(migrated["experimental_observations"]):
        if not isinstance(row, dict):
            raise HistoricalMigrationError(f"observation {index} is not an object")
        base = {**_audit_base(context, raw_response_path, row, index),
                "original_prompt_version": original_prompt_version,
                "original_prompt_hash": original_prompt_hash}
        for source, destination, rule in FIELD_MAPPINGS:
            _move(row, source, destination, rule, audit, base)

        provenance = row.get("provenance")
        if not isinstance(provenance, dict):
            raise HistoricalMigrationError("provenance must be an object")
        old_span = provenance.get("evidence_span")
        if "evidence_spans" in provenance and old_span is not None:
            raise HistoricalMigrationError("conflicting provenance.evidence_span and provenance.evidence_spans")
        if old_span is not None:
            span = locate_evidence_span(old_span, context.text, section=provenance.get("section") or provenance.get("source_section"))
            provenance["evidence_spans"] = [span]
            provenance.pop("evidence_span")
            audit.append({**base, "original_field_path": "provenance.evidence_span", "original_value": old_span,
                          "destination_field_path": "provenance.evidence_spans", "migrated_value": [span],
                          "migration_rule": "verbatim_span_to_singleton_v1", "value_source": "historical_raw_response",
                          "evidence_span_match_status": "exact", "source_start": span["char_start"],
                          "source_end": span["char_end"], "source_text_hash": _sha256(context.text)})
        spans = provenance.get("evidence_spans")
        if not isinstance(spans, list) or not spans:
            raise HistoricalMigrationError("evidence_span_missing")
        checked_spans = []
        for item in spans:
            raw_text = item.get("text") if isinstance(item, dict) else item
            checked_spans.append(locate_evidence_span(raw_text, context.text,
                                                      section=item.get("section") if isinstance(item, dict) else None))
        provenance["evidence_spans"] = checked_spans

        # Identity and document provenance come exclusively from trusted pipeline artifacts.
        trusted = {"paper_id": context.paper_id, "pmid": context.pmid, "pmcid": context.pmcid,
                   "source_document_id": context.source_document_id,
                   "fulltext_source_hash": context.fulltext_source_hash}
        for field, value in trusted.items():
            provenance[field] = value
            audit.append({**base, "original_field_path": None, "original_value": None,
                          "destination_field_path": f"provenance.{field}", "migrated_value": value,
                          "migration_rule": "trusted_pipeline_provenance_v1", "value_source": "pipeline_metadata",
                          "source_artifact": context.source_artifact, "source_hash": context.fulltext_source_hash})

        observation = row.get("observation")
        if not isinstance(observation, dict):
            raise HistoricalMigrationError("observation must be an object")
        if "direction" in observation:
            raw_direction = observation["direction"]
            if raw_direction is None:
                observation.pop("direction")
            else:
                result = DIRECTION_TO_OBSERVED_RESULT.get(str(raw_direction).strip().casefold())
                if result is None:
                    raise HistoricalMigrationError(f"observation.direction value is not equivalent: {raw_direction!r}")
                if observation.get("observed_result") not in (None, result):
                    raise HistoricalMigrationError("conflicting observation.direction and observation.observed_result")
                observation["observed_result"] = result
                observation.pop("direction")
                audit.append({**base, "original_field_path": "observation.direction", "original_value": raw_direction,
                              "destination_field_path": "observation.observed_result", "migrated_value": result,
                              "migration_rule": "equivalent_direction_text_v1", "value_source": "historical_raw_response"})
        if row.get("statement_role") == "current_study_experiment" and not observation.get("observation_span"):
            observation["observation_span"] = checked_spans[0]

        if row.get("author_interpretation") is None:
            row["author_interpretation"] = {}
        if row.get("candidate_relation") is None:
            row["candidate_relation"] = {}
        if not row.get("observation_id"):
            generated, details = deterministic_observation_id(row, context, checked_spans[0])
            row["observation_id"] = generated
            audit.append({**base, "original_field_path": None, "original_value": None,
                          "destination_field_path": "observation_id", "migrated_value": generated,
                          "migration_rule": OBSERVATION_ID_VERSION, "value_source": "deterministic_generation",
                          "generated_observation_id_inputs": details["inputs"],
                          "generated_observation_id_inputs_hash": details["inputs_hash"]})

    try:
        validated = FulltextL1V2Response.model_validate(migrated)
    except ValidationError as exc:
        raise HistoricalMigrationError(str(exc)) from exc
    return validated.model_dump(mode="json"), audit
