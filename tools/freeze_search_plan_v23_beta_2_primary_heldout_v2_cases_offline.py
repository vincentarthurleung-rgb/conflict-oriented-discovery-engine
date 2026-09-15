#!/usr/bin/env python3
"""Freeze fresh primary held-out-v2 scientific cases without query-layer use."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code_engine.search.historical_manifest_verifier import verify_frozen_manifest
from tools import freeze_search_plan_v23_beta_protocol_offline as beta


RUN = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_case_freeze_offline"
BETA2_RUN = ROOT / "runs/20260916_search_plan_v23_beta_2_modular_query_compiler_freeze_offline"
BETA_PROTOCOL_RUN = ROOT / "runs/20260915_search_plan_v23_beta_protocol_freeze_offline"
HELDOUT_V1_TARGETS = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline/heldout_scientific_targets.jsonl"
RETIRED_V2_TARGETS = ROOT / "runs/20260915_search_plan_v23_beta_heldout_v2_case_freeze_offline/heldout_v2_scientific_targets.jsonl"

EXPECTED_ROOTS = {
    "scientific_target_query_binding_v1_1_sha256": "87079f3fa7ab7cf3cf5f0cb36b1b136570526bd9317505ce5efd2d65ca0b052c",
    "query_family_applicability_v1_sha256": "940839883773179349f0b0c3589fa0bc168522ef1703237da82be8021cc26db7",
    "modular_query_compiler_v23_beta2_sha256": "6b1981285016a4f250f9cc7cc79dfe7acbe40ce807ec952b95ca1a1d87b63665",
    "search_plan_v23_beta_2_protocol_sha256": "3033bd951cd3b296a6e8aeb6d08a9a5367e58faaa41669619b99f0df7691a835",
}
EXPECTED_BASE_BETA_ROOT = "2bf89cca40c892307968cd279052ec1945d3c59940a785111b2e0de13eebf766"
SEARCH_PLAN_VERSION = "v2.3-beta.2"
CREATED_AT = "2026-09-16T00:00:00+08:00"
CASE_IDS = [f"heldout_v2_{index}" for index in range(101, 109)]
RETIRED_IDS = [f"heldout_v2_{index:03d}" for index in range(1, 9)]

REQUIRED = {
    "primary_heldout_v2_cases.json",
    "primary_heldout_v2_scientific_targets.jsonl",
    "primary_heldout_v2_case_selection_rationale.json",
    "primary_heldout_v2_case_selection_rationale.md",
    "heldout_v1_nonoverlap_audit.json",
    "retired_v2_nonoverlap_audit.json",
    "upstream_architecture_root_verification.json",
    "scientific_state_safety_audit.json",
    "freeze_manifest.json",
    "validation.json",
    "summary.json",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        for row in rows
    ).encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def aggregate(pairs: list[list[str]]) -> str:
    return sha_bytes(canonical(pairs))


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def target(
    case_id: str,
    subject: str,
    relation: str,
    measurement: str,
    endpoint: str,
    contexts: dict[str, list[str]],
    evidence_mode: str,
    acceptable: list[str],
    insufficient: list[str],
    meaning: str,
    *,
    subject_intervention: str,
    therapy: str | None = None,
    canonical_orientation: str | None = None,
    boundaries: list[str] | None = None,
) -> dict[str, Any]:
    flattened_contexts = [value for dimension in contexts.values() for value in dimension]
    return {
        "artifact_schema_version": "ScientificPropositionTargetV1",
        "scientific_proposition_target_id": f"{case_id}:scientific_proposition:v1",
        "case_id": case_id,
        "subject": subject,
        "canonical_subject": subject,
        "relation_family": relation,
        "canonical_relation_family": relation,
        "object": measurement,
        "measurement_target": measurement,
        "measurement_property_endpoint": endpoint,
        "context_qualifiers": flattened_contexts,
        "context_qualifier_dimensions": contexts,
        "subject_intervention": subject_intervention,
        "therapy": therapy,
        "canonical_proposition_orientation": canonical_orientation,
        "required_evidence_mode": evidence_mode,
        "acceptable_endpoint_evidence": acceptable,
        "insufficient_evidence": insufficient,
        "scientific_boundaries": boundaries or insufficient,
        "primary_proposition_meaning": meaning,
        "primary_evidence_required": True,
        "retrieval_membership_grants_compatibility": False,
        "frozen": True,
    }


def build_targets() -> list[dict[str, Any]]:
    return [
        target(
            "heldout_v2_101", "EGF", "increases", "ERK1/2", "phosphorylation",
            {"biological_unit": ["epidermal keratinocyte"], "treatment": ["EGF stimulation"]},
            "current-study perturbational evidence linking EGF exposure to increased ERK1/2 phosphorylation in keratinocytes",
            ["phospho-ERK1/2", "phosphorylated ERK1/2", "explicitly resolved ERK activation measured through phosphorylation"],
            ["total ERK abundance", "EGFR phosphorylation only", "generic MAPK pathway activation", "proliferation without ERK phosphorylation", "EGF/ERK association without perturbational linkage", "ERK phosphorylation in an incompatible biological unit"],
            "EGF increases ERK1/2 phosphorylation in epidermal keratinocytes.",
            subject_intervention="EGF stimulation or exposure",
            boundaries=["ERK phosphorylation is required; total ERK, EGFR phosphorylation, generic MAPK activation, and proliferation are not substitutes", "the biological unit must be epidermal keratinocyte or explicitly compatible", "current-study perturbational linkage is required"],
        ),
        target(
            "heldout_v2_102", "IFN-γ", "increases", "HLA-DR", "cell-surface protein expression / abundance",
            {"biological_unit": ["monocyte"], "treatment": ["IFN-γ stimulation"]},
            "current-study IFN-γ perturbation linked to increased cell-surface or explicitly compatible protein-level HLA-DR expression in monocytes",
            ["surface HLA-DR abundance", "HLA-DR protein expression clearly tied to monocytes", "flow-cytometric HLA-DR expression"],
            ["HLA-DRA transcript without protein or surface evidence", "generic MHC-II pathway discussion", "other activation markers", "macrophage or dendritic-cell evidence without authorized monocyte compatibility", "IFN-γ association without perturbation"],
            "IFN-γ increases cell-surface HLA-DR expression in monocytes.",
            subject_intervention="IFN-γ stimulation",
            boundaries=["protein-level or cell-surface HLA-DR evidence is required", "transcript alone is insufficient", "monocyte biological-unit compatibility and current-study perturbation are required"],
        ),
        target(
            "heldout_v2_103", "Wnt3a", "increases", "β-catenin", "nuclear accumulation / nuclear localization",
            {"biological_unit": ["intestinal epithelial cell"], "treatment": ["Wnt3a stimulation"]},
            "current-study Wnt3a perturbation linked to increased nuclear β-catenin localization or accumulation",
            ["nuclear β-catenin", "nuclear accumulation", "nuclear translocation when the resulting nuclear endpoint is explicitly measured"],
            ["total β-catenin abundance", "membrane β-catenin", "Wnt target-gene expression without nuclear β-catenin measurement", "generic Wnt pathway activation", "β-catenin measurement in incompatible biological units"],
            "Wnt3a increases nuclear β-catenin accumulation in intestinal epithelial cells.",
            subject_intervention="Wnt3a stimulation",
            boundaries=["abundance is not localization", "a nuclear β-catenin endpoint must be measured", "intestinal epithelial-cell compatibility and current-study perturbation are required"],
        ),
        target(
            "heldout_v2_104", "IL-1β", "increases", "PGE2 / prostaglandin E2", "secretion / extracellular release",
            {"biological_unit": ["articular chondrocyte"], "treatment": ["IL-1β stimulation"]},
            "current-study IL-1β perturbation linked to increased extracellular PGE2 release or secretion from chondrocytes",
            ["PGE2 measured in culture medium or supernatant", "explicitly extracellular PGE2 release", "compatible secretion readout"],
            ["COX-2 expression alone", "prostaglandin-pathway gene expression", "intracellular synthetic enzyme abundance", "generic inflammatory response", "PGE2 measurements in an incompatible biological unit"],
            "IL-1β increases PGE2 secretion from articular chondrocytes.",
            subject_intervention="IL-1β stimulation",
            boundaries=["pathway activation is not the secreted product endpoint", "extracellular PGE2 release or secretion is required", "articular chondrocyte compatibility and current-study perturbation are required"],
        ),
        target(
            "heldout_v2_105", "mTORC1", "inhibition increases", "autophagic flux", "dynamic autophagic degradation / flux",
            {"biological_unit": ["cardiomyocyte"]},
            "current-study reduction or inhibition of mTORC1 function linked to increased autophagic flux in cardiomyocytes or explicitly compatible cardiac myocyte models",
            ["target-specific mTORC1 inhibition with increased autophagic flux", "loss of an essential mTORC1 component when subject identity is deterministically resolved", "inverse perturbation evidence consistent with increased flux"],
            ["LC3-II abundance at a single time point without flux interpretation", "autophagosome number without dynamic flux evidence", "general autophagy-gene expression", "mitochondrial morphology", "cell survival alone", "mTOR pathway discussion without functional perturbation"],
            "mTORC1 inhibition increases autophagic flux in cardiomyocytes.",
            subject_intervention="mTORC1 inhibition or reduced mTORC1 activity",
            canonical_orientation="reduced mTORC1 activity -> increased autophagic flux",
            boundaries=["static autophagy markers are not autophagic flux", "mTORC1 identity and functional perturbation must be resolved", "cardiomyocyte or explicitly compatible cardiac-myocyte context is required"],
        ),
        target(
            "heldout_v2_106", "IL-10", "decreases / suppresses", "TNF-α", "secretion / extracellular release",
            {"biological_unit": ["macrophage"], "treatment_context": ["LPS stimulation"]},
            "current-study IL-10 perturbation linked to reduced TNF-α secretion under LPS-stimulated macrophage conditions",
            ["IL-10 treatment reducing LPS-induced extracellular TNF-α", "IL-10 pathway loss causing increased LPS-induced TNF secretion when directionally compatible", "necessity or rescue evidence"],
            ["basal TNF changes without LPS context", "TNF transcript alone", "other cytokines without TNF endpoint", "macrophage polarization markers", "IL-10/TNF association without functional perturbation"],
            "IL-10 suppresses LPS-induced TNF-α secretion in macrophages.",
            subject_intervention="IL-10 perturbation",
            canonical_orientation="increased IL-10 function -> decreased LPS-induced extracellular TNF-α",
            boundaries=["the LPS-induced response context is required", "extracellular TNF-α rather than transcript alone is required", "functional perturbation and macrophage compatibility are required"],
        ),
        target(
            "heldout_v2_107", "SHP2 / PTPN11", "inhibition increases sensitivity / sensitizes", "trametinib treatment response", "increased sensitivity / decreased resistance",
            {"disease_context": ["pancreatic ductal adenocarcinoma"], "genotype_context": ["KRAS-mutant"], "therapy": ["trametinib"]},
            "current-study functional evidence linking SHP2 inhibition or loss to increased trametinib response in the required pancreatic ductal adenocarcinoma and KRAS-mutant context",
            ["selective SHP2 inhibition plus trametinib sensitization", "SHP2 knockdown or depletion increasing trametinib response", "inverse or rescue evidence establishing SHP2 contribution"],
            ["SHP2 inhibition monotherapy viability", "trametinib response without SHP2 perturbation", "generic KRAS/MAPK signaling", "another MEK inhibitor without explicitly authorized therapy equivalence", "non-pancreatic KRAS-mutant tumor evidence", "SHP2 expression association without functional evidence"],
            "SHP2 inhibition increases trametinib sensitivity in KRAS-mutant pancreatic ductal adenocarcinoma cells.",
            subject_intervention="SHP2 inhibition or loss",
            therapy="trametinib",
            canonical_orientation="reduced SHP2 function -> increased trametinib sensitivity",
            boundaries=["therapy identity is trametinib unless equivalence is explicitly authorized", "both pancreatic ductal adenocarcinoma and KRAS-mutant contexts are required", "target-specific functional SHP2 perturbation and treatment-response contrast are required"],
        ),
        target(
            "heldout_v2_108", "PARP1", "inhibition increases sensitivity / sensitizes", "temozolomide treatment response", "increased sensitivity / decreased resistance",
            {"disease_context": ["glioblastoma"], "biological_unit": ["glioblastoma cell / explicitly compatible glioblastoma model"], "therapy": ["temozolomide"]},
            "current-study functional evidence linking PARP1 inhibition or loss to increased temozolomide response",
            ["PARP1-selective inhibition combined with temozolomide", "PARP1 depletion or knockdown increasing temozolomide sensitivity", "compatible necessity, rescue, or inverse perturbation evidence"],
            ["PARP inhibitor monotherapy cytotoxicity", "temozolomide response without PARP1 perturbation", "generic DNA-damage signaling", "another alkylating agent", "generic PARP-family inhibition when PARP1 identity cannot be resolved", "PARP1 expression correlation without functional evidence"],
            "PARP1 inhibition increases temozolomide sensitivity in glioblastoma cells.",
            subject_intervention="PARP1 inhibition or loss",
            therapy="temozolomide",
            canonical_orientation="reduced PARP1 function -> increased temozolomide sensitivity",
            boundaries=["generic viability reduction is not automatically temozolomide sensitization", "PARP1 identity and temozolomide therapy identity must be resolved", "functional perturbation and glioblastoma-cell compatibility are required"],
        ),
    ]


CASE_META = [
    ("heldout_v2_101", "LOW", "non_oncology", "single perturbation, direct molecular phosphorylation endpoint, and a relatively simple biological-unit constraint"),
    ("heldout_v2_102", "LOW", "non_oncology", "single perturbation, direct protein-expression endpoint, and a relatively simple biological-unit constraint"),
    ("heldout_v2_103", "MEDIUM", "non_oncology", "requires nuclear-localization semantics in addition to subject and relation matching"),
    ("heldout_v2_104", "MEDIUM", "non_oncology", "requires extracellular-secretion semantics rather than pathway or enzyme-expression evidence"),
    ("heldout_v2_105", "HIGH", "non_oncology", "requires a dynamic functional flux endpoint, target-specific inhibition, and compatible inverse perturbation reasoning"),
    ("heldout_v2_106", "HIGH", "non_oncology", "requires a nested LPS stimulation context, extracellular secretion, and directional perturbation reasoning"),
    ("heldout_v2_107", "HIGH", "oncology", "requires target-specific sensitization, therapy identity, disease context, and genotype context"),
    ("heldout_v2_108", "HIGH", "oncology", "requires PARP1-specific functional perturbation, therapy identity, disease context, and sensitization rather than generic viability"),
]


def build_cases(targets: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {row["case_id"]: row for row in targets}
    cases = []
    for order, (case_id, ambiguity, domain, rationale) in enumerate(CASE_META, 1):
        cases.append({
            "case_order": order,
            "case_id": case_id,
            "ambiguity_tier": ambiguity,
            "domain": domain,
            "oncology_case": domain == "oncology",
            "scientific_proposition": by_id[case_id]["primary_proposition_meaning"],
            "scientific_target_ref": f"primary_heldout_v2_scientific_targets.jsonl#{by_id[case_id]['scientific_proposition_target_id']}",
            "difficulty_rationale": rationale,
            "selection_type": "structured_prospective_scientific_case_selection",
            "primary_heldout_status": "frozen_primary_pre_query",
            "replacement_allowed_after_exposure": False,
        })
    return {
        "artifact_schema_version": "PrimaryHeldoutV2CasesV1",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "selection_type": "structured_prospective_scientific_case_selection",
        "random_sampling_claimed": False,
        "case_count": len(cases),
        "cases": cases,
    }


def exact_triple(row: dict[str, Any]) -> tuple[str, str, str]:
    subject = row.get("canonical_subject") or row["subject"]
    relation = row.get("canonical_relation_family") or row["relation_family"]
    endpoint = f"{row['measurement_target']}|{row['measurement_property_endpoint']}"
    return norm(subject), norm(relation), norm(endpoint)


def nonoverlap_audit(
    fresh: list[dict[str, Any]],
    previous_path: Path,
    *,
    schema: str,
    prior_label: str,
) -> dict[str, Any]:
    previous = read_jsonl(previous_path)
    proposition_index = {norm(row["primary_proposition_meaning"]): row["case_id"] for row in previous}
    triple_index = {exact_triple(row): row["case_id"] for row in previous}
    proposition_overlaps = []
    triple_overlaps = []
    for row in fresh:
        if norm(row["primary_proposition_meaning"]) in proposition_index:
            proposition_overlaps.append({
                "fresh_case_id": row["case_id"],
                "prior_case_id": proposition_index[norm(row["primary_proposition_meaning"])],
            })
        if exact_triple(row) in triple_index:
            triple_overlaps.append({
                "fresh_case_id": row["case_id"],
                "prior_case_id": triple_index[exact_triple(row)],
            })
    shared_relations = sorted(
        {norm(row.get("canonical_relation_family") or row["relation_family"]) for row in fresh}
        & {norm(row.get("canonical_relation_family") or row["relation_family"]) for row in previous}
    )
    return {
        "artifact_schema_version": schema,
        "comparison_set": prior_label,
        "comparison_source": rel(previous_path),
        "comparison_source_sha256": sha(previous_path),
        "fresh_target_count": len(fresh),
        "prior_target_count": len(previous),
        "normalization": "deterministic lowercase alphanumeric lexical normalization; exact equality only",
        "exact_proposition_overlap": len(proposition_overlaps),
        "exact_proposition_overlap_records": proposition_overlaps,
        "exact_subject_relation_endpoint_triple_overlap": len(triple_overlaps),
        "exact_subject_relation_endpoint_triple_overlap_records": triple_overlaps,
        "shared_generic_relation_types": shared_relations,
        "shared_generic_concepts_do_not_invalidate_selection": True,
        "status": "PASS" if not proposition_overlaps and not triple_overlaps else "FAIL",
    }


def verify_architecture_roots() -> dict[str, Any]:
    manifest = json.loads((BETA2_RUN / "version_manifest.json").read_bytes())
    mapping = [
        ("scientific_target_query_binding_v1_1_sha256", "scientific_target_query_binding_v1_1_components"),
        ("query_family_applicability_v1_sha256", "query_family_applicability_v1_components"),
        ("modular_query_compiler_v23_beta2_sha256", "modular_query_compiler_v23_beta2_components"),
        ("search_plan_v23_beta_2_protocol_sha256", "search_plan_v23_beta_2_protocol_components"),
    ]
    verified = {}
    for root_field, component_field in mapping:
        actual = aggregate(manifest[component_field])
        require(actual == manifest[root_field] == EXPECTED_ROOTS[root_field], f"root mismatch: {root_field}")
        verified[root_field] = {
            "status": "PASS",
            "expected_sha256": EXPECTED_ROOTS[root_field],
            "actual_sha256": actual,
            "component_count": len(manifest[component_field]),
        }
        for path_name, expected in manifest[component_field]:
            if "/" in path_name:
                path = ROOT / path_name
            elif path_name.endswith(".json"):
                path = BETA2_RUN / path_name
            else:
                continue
            require(path.is_file() and not path.is_symlink(), f"protected component unavailable: {path_name}")
            require(sha(path) == expected, f"protected component changed: {path_name}")

    base = verify_frozen_manifest(
        BETA_PROTOCOL_RUN,
        manifest_name="version_manifest.json",
        root_field="search_plan_v23_beta_protocol_sha256",
    )
    require(base["aggregate_sha256"] == EXPECTED_BASE_BETA_ROOT, "base beta protocol root mismatch")
    science_roots = beta.verify_upstreams()
    return {
        "artifact_schema_version": "UpstreamArchitectureRootVerificationV1",
        "architecture_roots": verified,
        "original_v23_beta_protocol": {"status": "PASS", "sha256": base["aggregate_sha256"]},
        "original_scientific_component_roots": science_roots,
        "all_four_exact_roots_verified": True,
        "query_binding_executed": False,
        "query_applicability_evaluated": False,
        "queries_compiled": False,
    }


def protected_state() -> dict[str, str]:
    paths = []
    for run in (BETA2_RUN, BETA_PROTOCOL_RUN, RETIRED_V2_TARGETS.parent):
        paths.extend(path for path in run.iterdir() if path.is_file())
    paths.extend([HELDOUT_V1_TARGETS])
    beta2_manifest = json.loads((BETA2_RUN / "version_manifest.json").read_bytes())
    for component_field in (
        "scientific_target_query_binding_v1_1_components",
        "query_family_applicability_v1_components",
        "modular_query_compiler_v23_beta2_components",
    ):
        for path_name, _ in beta2_manifest[component_field]:
            if "/" in path_name:
                paths.append(ROOT / path_name)
    base_manifest = json.loads((BETA_PROTOCOL_RUN / "version_manifest.json").read_bytes())
    paths.extend(ROOT / row["path"] for row in base_manifest["production_candidate_files"])
    return {rel(path): sha(path) for path in sorted(set(paths))}


def rationale_artifacts(cases: dict[str, Any]) -> tuple[dict[str, Any], str]:
    payload = {
        "artifact_schema_version": "PrimaryHeldoutV2CaseSelectionRationaleV1",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "selection_type": "structured_prospective_scientific_case_selection",
        "random_sampling_claimed": False,
        "case_count": 8,
        "difficulty_structure": {"LOW": 2, "MEDIUM": 2, "HIGH": 4},
        "domain_structure": {"oncology": 2, "non_oncology": 6},
        "cases": [
            {"case_id": row["case_id"], "ambiguity_tier": row["ambiguity_tier"],
             "domain": row["domain"], "scientific_rationale": row["difficulty_rationale"]}
            for row in cases["cases"]
        ],
        "selection_independence": {
            "ScientificTargetQueryBindingV1_1_executed": False,
            "QueryFamilyApplicabilityV1_executed": False,
            "SearchPlanQueryCompilerV23Beta2_executed": False,
            "alias_coverage_inspected": False,
            "broader_hierarchy_coverage_inspected": False,
            "family_applicability_inspected": False,
            "query_count_inspected": False,
            "pubmed_yield_inspected": False,
            "oa_availability_inspected": False,
            "candidate_titles_inspected": False,
            "candidate_relevance_inspected": False,
        },
        "case_replacement_performed": False,
    }
    lines = [
        "# Fresh primary held-out-v2 case selection rationale",
        "",
        "Selection type: structured prospective scientific case selection. No random-sampling claim is made.",
        "",
        "| Order | Case | Difficulty | Domain | Scientific rationale |",
        "|---:|---|---|---|---|",
    ]
    for row in cases["cases"]:
        lines.append(f"| {row['case_order']} | `{row['case_id']}` | {row['ambiguity_tier']} | {row['domain']} | {row['difficulty_rationale']} |")
    lines.extend([
        "",
        "The cases were selected without executing binding, applicability, or query compilation and without inspecting alias coverage, broader hierarchy coverage, expected query count, PubMed yield, OA availability, titles, or relevance.",
        "",
        "The retired initial held-out-v2 cases remain non-primary. No case may be replaced later because of optional family non-applicability or query-layer coverage.",
        "",
    ])
    return payload, "\n".join(lines)


def build_outputs(upstream: dict[str, Any], before: dict[str, str]) -> dict[str, bytes]:
    targets = build_targets()
    cases = build_cases(targets)
    v1_audit = nonoverlap_audit(
        targets, HELDOUT_V1_TARGETS,
        schema="HeldoutV1ToFreshPrimaryV2NonOverlapAuditV1",
        prior_label="frozen_heldout_v1_primary",
    )
    retired_audit = nonoverlap_audit(
        targets, RETIRED_V2_TARGETS,
        schema="RetiredV2ToFreshPrimaryV2NonOverlapAuditV1",
        prior_label="retired_initial_heldout_v2",
    )
    require(v1_audit["status"] == retired_audit["status"] == "PASS", "exact prior-case overlap")
    prior_ids = {row["case_id"] for row in read_jsonl(HELDOUT_V1_TARGETS) + read_jsonl(RETIRED_V2_TARGETS)}
    id_collisions = sorted(set(CASE_IDS) & prior_ids)
    require(not id_collisions, "fresh case ID collision")

    rationale_json, rationale_md = rationale_artifacts(cases)
    ambiguity = Counter(row["ambiguity_tier"] for row in cases["cases"])
    domains = Counter(row["domain"] for row in cases["cases"])
    required_target_fields = {
        "case_id", "subject", "relation_family", "object", "measurement_target",
        "measurement_property_endpoint", "context_qualifiers", "context_qualifier_dimensions",
        "required_evidence_mode", "acceptable_endpoint_evidence", "insufficient_evidence",
        "scientific_boundaries", "primary_proposition_meaning", "frozen",
    }
    complete_targets = all(required_target_fields <= set(row) and all(
        row[field] for field in (
            "subject", "relation_family", "object", "measurement_target",
            "measurement_property_endpoint", "context_qualifiers", "required_evidence_mode",
            "acceptable_endpoint_evidence", "insufficient_evidence", "scientific_boundaries",
            "primary_proposition_meaning",
        )
    ) for row in targets)

    safety = {
        "artifact_schema_version": "PrimaryHeldoutV2CaseFreezeSafetyAuditV1",
        "mode": "offline_scientific_case_selection_only",
        "upstream_architecture_roots": EXPECTED_ROOTS,
        "historical_protected_state_before": before,
        "search_plan_v23_beta_2_modified": False,
        "binding_v1_1_modified": False,
        "applicability_v1_modified": False,
        "modular_compiler_modified": False,
        "p0_modified": False,
        "p1_modified": False,
        "p2_modified": False,
        "policy_a_modified": False,
        "metrics_spec_v2_modified": False,
        "adjudication_boundary_v2_modified": False,
        "retired_cases_modified": False,
        "query_binding_executed": False,
        "query_applicability_evaluated": False,
        "queries_compiled": False,
        "retrieval_started": False,
        "network_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "downloads": 0,
        "retrieval_calls": 0,
        "candidate_records_seen": 0,
        "historical_assets_modified": False,
    }
    checks = {
        "all_four_architecture_roots_verified": upstream["all_four_exact_roots_verified"],
        "case_count_8": len(targets) == len(cases["cases"]) == 8,
        "canonical_case_ids_and_order": [row["case_id"] for row in cases["cases"]] == CASE_IDS,
        "difficulty_counts_2_2_4": dict(ambiguity) == {"LOW": 2, "MEDIUM": 2, "HIGH": 4},
        "domain_counts_2_6": dict(domains) == {"non_oncology": 6, "oncology": 2},
        "fresh_case_id_collision_zero": not id_collisions,
        "all_required_target_fields_complete": complete_targets,
        "all_evidence_mode_boundaries_explicit": all(row["required_evidence_mode"] and row["insufficient_evidence"] and row["scientific_boundaries"] for row in targets),
        "all_required_context_qualifiers_explicit": all(row["context_qualifiers"] and row["context_qualifier_dimensions"] for row in targets),
        "heldout_v1_exact_overlap_zero": v1_audit["exact_proposition_overlap"] == v1_audit["exact_subject_relation_endpoint_triple_overlap"] == 0,
        "retired_v2_exact_overlap_zero": retired_audit["exact_proposition_overlap"] == retired_audit["exact_subject_relation_endpoint_triple_overlap"] == 0,
        "no_query_layer_execution": not any((safety["query_binding_executed"], safety["query_applicability_evaluated"], safety["queries_compiled"])),
        "no_case_replacement": not rationale_json["case_replacement_performed"],
        "offline_counters_zero": True,
        "deterministic_double_generation": True,
    }
    validation = {
        "artifact_schema_version": "PrimaryHeldoutV2CaseFreezeValidationV1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "case_count": len(targets),
        "difficulty_counts": dict(sorted(ambiguity.items())),
        "domain_counts": dict(sorted(domains.items())),
        "fresh_case_id_collision": len(id_collisions),
    }
    require(validation["status"] == "PASS", "case-freeze validation failed")

    outputs = {
        "primary_heldout_v2_cases.json": pretty(cases),
        "primary_heldout_v2_scientific_targets.jsonl": jsonl(targets),
        "primary_heldout_v2_case_selection_rationale.json": pretty(rationale_json),
        "primary_heldout_v2_case_selection_rationale.md": (rationale_md + "\n").encode("utf-8"),
        "heldout_v1_nonoverlap_audit.json": pretty(v1_audit),
        "retired_v2_nonoverlap_audit.json": pretty(retired_audit),
        "upstream_architecture_root_verification.json": pretty(upstream),
        "scientific_state_safety_audit.json": pretty(safety),
        "validation.json": pretty(validation),
    }
    component_names = sorted(outputs)
    components = [[name, sha_bytes(outputs[name])] for name in component_names]
    freeze_root = aggregate(components)
    manifest = {
        "artifact_schema_version": "PrimaryHeldoutV2CaseFreezeManifestV1",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "created_at": CREATED_AT,
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_scope": "all required outputs except freeze_manifest.json and summary.json",
        "aggregate_components": components,
        "primary_heldout_v2_case_freeze_sha256": freeze_root,
        "required_outputs": sorted(REQUIRED),
        "upstream_architecture_roots": EXPECTED_ROOTS,
        "case_count": 8,
        "query_layer_execution": False,
    }
    outputs["freeze_manifest.json"] = pretty(manifest)
    summary = {
        "artifact_schema_version": "PrimaryHeldoutV2CaseFreezeSummaryV1",
        "status": "COMPLETED",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "case_count": 8,
        "low_count": ambiguity["LOW"],
        "medium_count": ambiguity["MEDIUM"],
        "high_count": ambiguity["HIGH"],
        "oncology_count": domains["oncology"],
        "non_oncology_count": domains["non_oncology"],
        "heldout_v1_exact_proposition_overlap": v1_audit["exact_proposition_overlap"],
        "heldout_v1_exact_subject_relation_endpoint_triple_overlap": v1_audit["exact_subject_relation_endpoint_triple_overlap"],
        "retired_v2_exact_proposition_overlap": retired_audit["exact_proposition_overlap"],
        "retired_v2_exact_subject_relation_endpoint_triple_overlap": retired_audit["exact_subject_relation_endpoint_triple_overlap"],
        "fresh_case_id_collision": len(id_collisions),
        "query_binding_executed": False,
        "query_applicability_evaluated": False,
        "queries_compiled": False,
        "retrieval_started": False,
        "primary_heldout_v2_case_freeze_sha256": freeze_root,
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0,
        "downloads": 0, "retrieval_calls": 0, "candidate_records_seen": 0,
        "historical_assets_modified": False,
    }
    outputs["summary.json"] = pretty(summary)
    require(set(outputs) == REQUIRED, f"required output mismatch: {sorted(set(outputs) ^ REQUIRED)}")
    return outputs


def main() -> None:
    if RUN.exists():
        unexpected = {path.name for path in RUN.iterdir()} - REQUIRED
        require(not unexpected, f"output run contains unexpected files: {sorted(unexpected)}")
    upstream = verify_architecture_roots()
    before = protected_state()
    first = build_outputs(upstream, before)
    second = build_outputs(upstream, before)
    require(first == second, "double generation was not byte-identical")
    RUN.mkdir(parents=True, exist_ok=True)
    for name, body in sorted(first.items()):
        (RUN / name).write_bytes(body)
    require({path.name for path in RUN.iterdir()} == REQUIRED, "output membership mismatch")
    require(protected_state() == before, "historical protected assets changed")
    print(json.dumps(json.loads(first["summary.json"]), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
