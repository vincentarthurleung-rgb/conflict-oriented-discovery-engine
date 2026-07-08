"""LLM-assisted entity surface cleaner and verified normalization routing.

Conservative pre-step: LLM is ONLY allowed to:
  1. Extract head entities from noisy/long surfaces
  2. Expand aliases
  3. Classify entity types
  4. Suggest ontology/provider routes
  5. Separate modifiers/context from core entity mentions

LLM MUST NOT directly produce a final canonical_id.
Final canonical_id MUST come from PubChem / ChEMBL / MyGene / UniProt or
future ontology providers (MeSH, GO, Disease Ontology, Cell Ontology, etc.).
LLM-suggested but unverified results are never high-confidence graph eligible.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Supported entity types
# ---------------------------------------------------------------------------
SUPPORTED_ENTITY_TYPES: tuple[str, ...] = (
    "gene",
    "protein",
    "drug",
    "compound",
    "pathway",
    "biological_process",
    "phenotype",
    "disease",
    "cell_type",
    "tissue",
    "experimental_condition",
    "context",
    "unknown",
)

# ---------------------------------------------------------------------------
# Default provider routing map: entity_type -> preferred provider list
# ---------------------------------------------------------------------------
DEFAULT_ONTOLOGY_ROUTES: dict[str, list[str]] = {
    "gene": ["mygene", "uniprot"],
    "protein": ["uniprot", "mygene"],
    "drug": ["pubchem", "chembl"],
    "compound": ["pubchem", "chembl"],
    "pathway": [],           # future: Reactome, KEGG, WikiPathways
    "biological_process": [], # future: GO
    "phenotype": [],          # future: HPO, Disease Ontology
    "disease": [],            # future: Disease Ontology, MeSH, MONDO
    "cell_type": [],          # future: Cell Ontology
    "tissue": [],             # future: Uberon, MeSH
    "experimental_condition": [],
    "context": [],
    "unknown": [],
}

# ---------------------------------------------------------------------------
# Cleaner status values
# ---------------------------------------------------------------------------
CleanerStatus = Literal[
    "cleaned",
    "cleaned_with_warnings",
    "no_change_needed",
    "llm_unavailable",
    "llm_error",
    "disabled",
    "empty_surface",
]

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CleanedHeadEntity:
    """A single cleaned entity head extracted by the LLM cleaner."""
    surface: str
    aliases: list[str] = field(default_factory=list)
    entity_type: str = "unknown"
    ontology_routes: list[str] = field(default_factory=list)
    removed_modifiers: list[str] = field(default_factory=list)
    confidence: float = 0.0
    rationale_short: str = ""


@dataclass
class LLMCleanerResult:
    """Output from the LLM entity surface cleaner."""
    original_mention: str
    cleaned_head_entities: list[CleanedHeadEntity] = field(default_factory=list)
    residual_context: str = ""
    llm_cleaner_status: CleanerStatus = "disabled"
    warnings: list[str] = field(default_factory=list)
    # Audit trail
    claim_id: str | None = None
    observation_id: str | None = None
    mention_role: str | None = None
    l1_entity_type_hint: str | None = None
    surrounding_context: str = ""
    # External verification tracking (populated post-cleaner by hub)
    external_verification_result: str | None = None  # "verified" | "unverified" | "ambiguous" | "provider_no_result"
    final_decision: str | None = None
    high_confidence_graph_allowed: bool = False
    rejection_reason: str | None = None


# ---------------------------------------------------------------------------
# Deterministic pre-cleaning (no LLM needed)
# ---------------------------------------------------------------------------

# Common modifier/context phrases that should be stripped from entity surfaces
MODIFIER_PATTERNS: list[tuple[str, str]] = [
    # (regex pattern, description)
    (r"\bthe\s+(therapeutic|treatment)\s+effect\s+of\s+", "therapeutic_effect_modifier"),
    (r"\bthe\s+role\s+of\s+", "role_modifier"),
    (r"\bthe\s+(expression|overexpression|upregulation|downregulation)\s+of\s+", "expression_modifier"),
    (r"\bthe\s+(inhibition|activation|suppression|induction)\s+of\s+", "regulation_modifier"),
    (r"\bthe\s+(level|levels|activity)\s+of\s+", "level_modifier"),
    (r"\bthe\s+(function|dysfunction)\s+of\s+", "function_modifier"),
    (r"\bthe\s+(presence|absence)\s+of\s+", "presence_modifier"),
    (r"\bthe\s+(production|secretion|release)\s+of\s+", "production_modifier"),
    (r"\bthe\s+(development|progression)\s+of\s+", "development_modifier"),
    (r"\bthe\s+(response|resistance)\s+to\s+", "response_modifier"),
    (r"\bthe\s+(expression|overexpression|knockdown|silencing)\s+of\s+", "genetic_modifier"),
    (r"\boverexpression\s+of\s+", "overexpression_modifier"),
    (r"\bknockdown\s+of\s+", "knockdown_modifier"),
    (r"\bsilencing\s+of\s+", "silencing_modifier"),
    (r"\binhibition\s+of\s+", "inhibition_modifier"),
    (r"\bactivation\s+of\s+", "activation_modifier"),
    (r"\bupregulation\s+of\s+", "upregulation_modifier"),
    (r"\bdownregulation\s+of\s+", "downregulation_modifier"),
    (r"\bphosphorylation\s+of\s+", "phosphorylation_modifier"),
    (r"\bexpression\s+of\s+", "expression_modifier"),
    (r"\bthe\s+role\s+of\s+", "role_modifier"),
    (r"\bthe\s+(effect|effects|impact)\s+of\s+", "effect_modifier"),
]

# Known alias expansions (deterministic, no LLM)
KNOWN_ALIASES: dict[str, list[str]] = {
    "5-fluorouracil": ["5-FU", "5FU", "fluorouracil", "adrucil"],
    "epithelial-mesenchymal transition": ["EMT", "epithelial to mesenchymal transition"],
    "mitogen-activated protein kinase": ["MAPK", "MAP kinase"],
    "reactive oxygen species": ["ROS"],
    "programmed death-ligand 1": ["PD-L1", "CD274", "B7-H1"],
    "vascular endothelial growth factor": ["VEGF"],
    "epidermal growth factor receptor": ["EGFR", "ERBB1", "HER1"],
    "nuclear factor kappa B": ["NF-κB", "NF-kB", "NFKB"],
    "phosphatidylinositol 3-kinase": ["PI3K", "PI3 kinase"],
    "protein kinase B": ["AKT", "PKB"],
    "mechanistic target of rapamycin": ["mTOR", "FRAP1"],
    "signal transducer and activator of transcription 3": ["STAT3"],
    "hypoxia-inducible factor 1 alpha": ["HIF-1α", "HIF1A", "HIF-1alpha"],
    "interleukin 6": ["IL-6", "IL6"],
    "transforming growth factor beta": ["TGF-β", "TGF-beta", "TGFB"],
    "tumor necrosis factor": ["TNF", "TNF-alpha", "TNF-α"],
    "tumor protein p53": ["TP53", "p53"],
    "cyclin-dependent kinase inhibitor 1A": ["CDKN1A", "p21", "WAF1", "CIP1"],
    "B-cell lymphoma 2": ["BCL2", "Bcl-2"],
    "Bcl-2-associated X protein": ["BAX"],
    "caspase 3": ["CASP3"],
    "phosphatase and tensin homolog": ["PTEN"],
    "cancer stem cell": ["CSC", "tumor-initiating cell"],
}


def _deterministic_clean(surface: str) -> tuple[str, list[str], list[str]]:
    """Deterministic pre-cleaning: remove common modifiers, extract head.

    Returns (cleaned_surface, removed_modifiers, found_aliases).
    """
    import re
    original = surface.strip()
    cleaned = original
    removed: list[str] = []
    found_aliases: list[str] = []

    # Apply modifier patterns
    for pattern, desc in MODIFIER_PATTERNS:
        m = re.match(pattern, cleaned, re.IGNORECASE)
        if m:
            removed.append(desc)
            cleaned = cleaned[m.end():].strip()

    # Check known aliases
    cleaned_lower = cleaned.casefold()
    for canonical, aliases in KNOWN_ALIASES.items():
        if cleaned_lower == canonical.casefold():
            found_aliases.extend(aliases)
            break
        for alias in aliases:
            if cleaned_lower == alias.casefold():
                found_aliases.append(canonical)
                found_aliases.extend(a for a in aliases if a.casefold() != cleaned_lower)
                break

    return cleaned, removed, found_aliases


def _infer_entity_type_heuristic(surface: str, l1_hint: str | None = None) -> str:
    """Heuristic entity type inference (no LLM, fast fallback)."""
    if l1_hint and l1_hint != "unknown":
        return l1_hint

    text = surface.casefold().strip()

    # Gene/protein patterns: all-caps short names, gene symbols
    import re
    if re.fullmatch(r"[A-Z][A-Z0-9]{1,8}", surface.strip()):
        return "gene"
    if re.fullmatch(r"[a-z]{3,5}-[0-9]+[a-z]?", surface.strip()):
        return "gene"  # e.g., bcl-2, p53-like

    # Drug/compound patterns
    if re.search(r"(\d+-)?[A-Z]{2,}\d+", surface.strip()):  # e.g., SB203580, LY294002
        return "compound"

    # Pathway patterns
    if any(term in text for term in ("pathway", "signaling", "signalling", "cascade")):
        return "pathway"

    # Biological process patterns
    if text.endswith(("tion", "sis", "ment", "ance", "ing")):
        return "biological_process"

    # Disease/phenotype patterns
    if any(term in text for term in ("cancer", "carcinoma", "tumor", "tumour", "disease", "syndrome", "disorder")):
        return "disease"

    # Cell type patterns
    if any(term in text for term in ("cell", "cyte", "blast", "phage", "phil")):
        return "cell_type"

    # Experimental condition
    if any(term in text for term in ("hypoxia", "normoxia", "serum", "treated", "stimulated", "induced", "exposed")):
        return "experimental_condition"

    return "unknown"


def _route_entity_type(entity_type: str) -> list[str]:
    """Return preferred provider routes for a given entity type."""
    return DEFAULT_ONTOLOGY_ROUTES.get(entity_type, [])


# ---------------------------------------------------------------------------
# LLM prompt template
# ---------------------------------------------------------------------------

ENTITY_CLEANER_SYSTEM_PROMPT = """You are a conservative biomedical entity surface cleaner. Your ONLY job is to extract and normalize entity mentions from noisy text.

RULES (STRICT):
1. Extract the HEAD biomedical entity from the mention. Remove modifiers like "the therapeutic effect of", "overexpression of", "role of", "knockdown of", "inhibition of", etc.
2. Expand known abbreviations and provide aliases for the entity (e.g., "5-FU" -> "5-fluorouracil", "EMT" -> "epithelial-mesenchymal transition").
3. Classify the entity into exactly ONE of these types:
   - gene, protein, drug, compound, pathway, biological_process, phenotype, disease, cell_type, tissue, experimental_condition, context, unknown
4. Suggest which external providers should verify this entity:
   - gene -> mygene, uniprot
   - protein -> uniprot, mygene
   - drug -> pubchem, chembl
   - compound -> pubchem, chembl
   - pathway, biological_process, phenotype, disease, cell_type, tissue -> empty list (no external provider yet)
   - experimental_condition, context, unknown -> empty list
5. Separate residual context/modifier text from the core entity.
6. NEVER fabricate a canonical ID (like PMID, UniProt ID, PubChem CID). Only clean the surface.
7. If the mention is a multi-component pathway (like "GRB2-RAS-RAF-MEK-ERK pathway"), split into individual gene/protein heads.
8. Be conservative: if unsure, set entity_type to "unknown" and confidence low.

Return JSON with this exact schema:
{
  "cleaned_head_entities": [
    {
      "surface": "clean entity name",
      "aliases": ["alias1", "alias2"],
      "entity_type": "drug|gene|protein|etc",
      "ontology_routes": ["pubchem", "chembl"],
      "removed_modifiers": ["therapeutic effect"],
      "confidence": 0.85,
      "rationale_short": "brief explanation"
    }
  ],
  "residual_context": "remaining context after extraction"
}"""


def _build_cleaner_prompt(
    mention: str,
    claim_context: str = "",
    mention_role: str = "",
    l1_type_hint: str = "",
) -> str:
    """Build the LLM prompt for entity surface cleaning."""
    parts = [f"Original mention: {mention}"]
    if claim_context:
        parts.append(f"Surrounding context: {claim_context}")
    if mention_role:
        parts.append(f"Mention role: {mention_role}")
    if l1_type_hint and l1_type_hint != "unknown":
        parts.append(f"L1 type hint: {l1_type_hint}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# LLM Entity Cleaner (main class)
# ---------------------------------------------------------------------------

class LLMEntityCleaner:
    """Conservative LLM-assisted entity surface cleaner.

    This component:
      - Extracts head entities from noisy/long surfaces
      - Expands aliases
      - Classifies entity types
      - Suggests provider routes
      - Separates modifiers/context

    It NEVER produces a final canonical_id.
    """

    def __init__(
        self,
        llm_client: Any = None,
        *,
        enabled: bool = False,
        audit_dir: str | Path | None = None,
    ):
        self.llm_client = llm_client
        self.enabled = enabled
        self.audit_dir = Path(audit_dir) if audit_dir else None

        # Stats
        self.calls_made: int = 0
        self.cleaned_count: int = 0
        self.failed_count: int = 0
        self.suggested_unverified_count: int = 0
        self.external_verified_after_cleaning_count: int = 0
        self.external_lookup_after_cleaning_calls: int = 0

        # Audit records
        self._audit_records: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Stats / manifest helpers
    # ------------------------------------------------------------------

    def manifest_fields(self) -> dict[str, Any]:
        return {
            "entity_llm_cleaner_enabled": self.enabled,
            "entity_llm_cleaner_calls_made": self.calls_made,
            "entity_llm_cleaner_cleaned_count": self.cleaned_count,
            "entity_llm_cleaner_failed_count": self.failed_count,
            "entity_llm_suggested_unverified_count": self.suggested_unverified_count,
            "entity_external_verified_after_llm_cleaning_count": self.external_verified_after_cleaning_count,
            "entity_external_lookup_after_cleaning_calls_made": self.external_lookup_after_cleaning_calls,
        }

    # ------------------------------------------------------------------
    # Core cleaning logic
    # ------------------------------------------------------------------

    def clean(
        self,
        mention: str,
        *,
        claim_context: str = "",
        mention_role: str = "subject",
        l1_type_hint: str | None = None,
        claim_id: str | None = None,
        observation_id: str | None = None,
    ) -> LLMCleanerResult:
        """Clean an entity mention surface.

        Args:
            mention: The raw entity mention text.
            claim_context: Surrounding claim/evidence context.
            mention_role: "subject" or "object".
            l1_type_hint: Entity type hint from L1 extraction.
            claim_id: Claim ID for audit trail.
            observation_id: Observation ID for audit trail.

        Returns:
            LLMCleanerResult with cleaned entities and routing.
        """
        # Fast path: empty or whitespace
        if not mention or not mention.strip():
            return LLMCleanerResult(
                original_mention=mention,
                llm_cleaner_status="empty_surface",
                warnings=["empty_or_whitespace_surface"],
                claim_id=claim_id,
                observation_id=observation_id,
                mention_role=mention_role,
                l1_entity_type_hint=l1_type_hint,
                surrounding_context=claim_context,
            )

        # Fast path: disabled
        if not self.enabled:
            return LLMCleanerResult(
                original_mention=mention,
                llm_cleaner_status="disabled",
                warnings=["llm_cleaner_disabled"],
                claim_id=claim_id,
                observation_id=observation_id,
                mention_role=mention_role,
                l1_entity_type_hint=l1_type_hint,
                surrounding_context=claim_context,
            )

        # Step 1: Deterministic pre-cleaning (always runs, even without LLM)
        cleaned_surface, removed_mods, found_aliases = _deterministic_clean(mention)

        # Step 2: Try LLM if available
        llm_heads: list[CleanedHeadEntity] = []
        llm_status: CleanerStatus = "no_change_needed"
        llm_warnings: list[str] = []
        residual = ""

        if self.llm_client is not None:
            try:
                llm_heads, residual, llm_status, llm_warnings = self._call_llm(
                    mention=mention,
                    claim_context=claim_context,
                    mention_role=mention_role,
                    l1_type_hint=l1_type_hint or "",
                )
                self.calls_made += 1
            except Exception as exc:
                llm_status = "llm_error"
                llm_warnings = [f"llm_cleaner_error:{type(exc).__name__}:{str(exc)[:200]}"]
                self.failed_count += 1
        else:
            llm_status = "llm_unavailable"
            llm_warnings = ["llm_client_not_configured_fallback_to_deterministic"]

        # Step 3: Merge LLM results with deterministic pre-cleaning
        if llm_heads:
            # LLM produced results
            merged_heads = self._merge_heads(llm_heads, removed_mods, found_aliases)
            self.cleaned_count += 1
            status = "cleaned" if not llm_warnings else "cleaned_with_warnings"
        elif cleaned_surface != mention or found_aliases:
            # Deterministic only produced improvements
            merged_heads = [
                CleanedHeadEntity(
                    surface=cleaned_surface,
                    aliases=found_aliases,
                    entity_type=_infer_entity_type_heuristic(cleaned_surface, l1_type_hint),
                    ontology_routes=_route_entity_type(
                        _infer_entity_type_heuristic(cleaned_surface, l1_type_hint)
                    ),
                    removed_modifiers=removed_mods,
                    confidence=0.6,
                    rationale_short="deterministic_pre_cleaning_only",
                )
            ]
            self.cleaned_count += 1
            status = "cleaned_with_warnings"
            if not llm_warnings:
                llm_warnings.append("llm_unavailable_used_deterministic_fallback")
        else:
            # No cleaning needed or possible
            merged_heads = [
                CleanedHeadEntity(
                    surface=mention.strip(),
                    aliases=[],
                    entity_type=_infer_entity_type_heuristic(mention.strip(), l1_type_hint),
                    ontology_routes=_route_entity_type(
                        _infer_entity_type_heuristic(mention.strip(), l1_type_hint)
                    ),
                    removed_modifiers=[],
                    confidence=0.3,
                    rationale_short="no_cleaning_applied",
                )
            ]
            status = llm_status

        result = LLMCleanerResult(
            original_mention=mention,
            cleaned_head_entities=merged_heads,
            residual_context=residual,
            llm_cleaner_status=status,
            warnings=list(dict.fromkeys(llm_warnings)),
            claim_id=claim_id,
            observation_id=observation_id,
            mention_role=mention_role,
            l1_entity_type_hint=l1_type_hint,
            surrounding_context=claim_context,
        )

        # Record audit
        self._record_audit(result)
        return result

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        mention: str,
        claim_context: str,
        mention_role: str,
        l1_type_hint: str,
    ) -> tuple[list[CleanedHeadEntity], str, CleanerStatus, list[str]]:
        """Call the LLM and parse the response."""
        prompt = _build_cleaner_prompt(mention, claim_context, mention_role, l1_type_hint)

        # Build system + user messages
        messages = [
            {"role": "system", "content": ENTITY_CLEANER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        # Try extract_json first; fall back to raw completion
        try:
            response = self.llm_client.extract_json(messages)
        except (AttributeError, TypeError):
            # Fall back to chat completion
            raw = self.llm_client(messages)
            try:
                response = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                return [], "", "llm_error", ["llm_response_not_valid_json"]

        # Parse response
        heads: list[CleanedHeadEntity] = []
        warnings: list[str] = []
        raw_heads = response.get("cleaned_head_entities", [])
        if isinstance(raw_heads, dict):
            raw_heads = [raw_heads]
        if not isinstance(raw_heads, list):
            raw_heads = []

        for item in raw_heads:
            if not isinstance(item, dict):
                continue
            surface = str(item.get("surface", "")).strip()
            if not surface:
                continue

            entity_type = str(item.get("entity_type", "unknown")).strip().casefold()
            if entity_type not in SUPPORTED_ENTITY_TYPES:
                entity_type = "unknown"

            routes = item.get("ontology_routes", [])
            if isinstance(routes, str):
                routes = [routes]
            if not isinstance(routes, list):
                routes = []
            # Validate routes
            valid_routes = [r for r in routes if isinstance(r, str)]

            # Safety: ensure LLM didn't try to fabricate a canonical_id
            if item.get("canonical_id") or item.get("id"):
                warnings.append("llm_attempted_canonical_id_ignored")

            heads.append(
                CleanedHeadEntity(
                    surface=surface,
                    aliases=[str(a) for a in (item.get("aliases") or []) if isinstance(a, str)],
                    entity_type=entity_type,
                    ontology_routes=valid_routes,
                    removed_modifiers=[str(m) for m in (item.get("removed_modifiers") or []) if isinstance(m, str)],
                    confidence=max(0.0, min(1.0, float(item.get("confidence", 0.5)))),
                    rationale_short=str(item.get("rationale_short", "")),
                )
            )

        residual = str(response.get("residual_context", ""))

        if not heads:
            return [], "", "llm_error", ["llm_produced_no_valid_heads"]

        status: CleanerStatus = "cleaned" if not warnings else "cleaned_with_warnings"
        return heads, residual, status, warnings

    # ------------------------------------------------------------------
    # Merge LLM heads with deterministic results
    # ------------------------------------------------------------------

    def _merge_heads(
        self,
        llm_heads: list[CleanedHeadEntity],
        det_removed: list[str],
        det_aliases: list[str],
    ) -> list[CleanedHeadEntity]:
        """Merge LLM heads with deterministic pre-cleaning results."""
        merged = []
        for head in llm_heads:
            # Combine removed modifiers (deduplicate)
            all_removed = list(dict.fromkeys(det_removed + head.removed_modifiers))
            # Combine aliases (deduplicate, preserve order)
            all_aliases = list(dict.fromkeys(det_aliases + head.aliases))

            # Ensure ontology routes are set based on entity type
            if not head.ontology_routes:
                head.ontology_routes = _route_entity_type(head.entity_type)

            merged.append(
                CleanedHeadEntity(
                    surface=head.surface,
                    aliases=all_aliases,
                    entity_type=head.entity_type,
                    ontology_routes=head.ontology_routes,
                    removed_modifiers=all_removed,
                    confidence=head.confidence,
                    rationale_short=head.rationale_short,
                )
            )
        return merged

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def _record_audit(self, result: LLMCleanerResult) -> None:
        """Record audit entry for this cleaning operation."""
        record = {
            "original_mention": result.original_mention,
            "normalized_mention": (
                result.cleaned_head_entities[0].surface
                if result.cleaned_head_entities
                else result.original_mention
            ),
            "claim_id": result.claim_id,
            "observation_id": result.observation_id,
            "mention_role": result.mention_role,
            "l1_entity_type_hint": result.l1_entity_type_hint,
            "surrounding_context": result.surrounding_context,
            "llm_cleaned_head_entities": [
                {
                    "surface": h.surface,
                    "aliases": h.aliases,
                    "entity_type": h.entity_type,
                    "ontology_routes": h.ontology_routes,
                    "removed_modifiers": h.removed_modifiers,
                    "confidence": h.confidence,
                    "rationale_short": h.rationale_short,
                }
                for h in result.cleaned_head_entities
            ],
            "provider_routes": list(
                dict.fromkeys(
                    route
                    for h in result.cleaned_head_entities
                    for route in h.ontology_routes
                )
            ),
            "external_verification_result": result.external_verification_result,
            "final_decision": result.final_decision,
            "high_confidence_graph_allowed": result.high_confidence_graph_allowed,
            "rejection_reason": result.rejection_reason,
            "llm_cleaner_status": result.llm_cleaner_status,
            "warnings": result.warnings,
        }
        self._audit_records.append(record)

    def write_audit_files(self, artifacts_dir: Path) -> dict[str, str]:
        """Write all audit files to the artifacts directory."""
        artifacts_dir = Path(artifacts_dir)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        paths: dict[str, str] = {}

        # Write llm_cleaner_audit.jsonl
        audit_jsonl = artifacts_dir / "entity_llm_cleaner_audit.jsonl"
        with audit_jsonl.open("a", encoding="utf-8") as f:
            for record in self._audit_records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        paths["entity_llm_cleaner_audit_jsonl"] = str(audit_jsonl)

        # Write summary
        summary = {
            **self.manifest_fields(),
            "total_audit_records": len(self._audit_records),
            "status_distribution": {
                status: sum(
                    1 for r in self._audit_records if r.get("llm_cleaner_status") == status
                )
                for status in ("cleaned", "cleaned_with_warnings", "no_change_needed",
                               "llm_unavailable", "llm_error", "disabled", "empty_surface")
            },
            "verification_distribution": {
                "verified": sum(1 for r in self._audit_records if r.get("external_verification_result") == "verified"),
                "unverified": sum(1 for r in self._audit_records if r.get("external_verification_result") == "unverified"),
                "ambiguous": sum(1 for r in self._audit_records if r.get("external_verification_result") == "ambiguous"),
                "provider_no_result": sum(1 for r in self._audit_records if r.get("external_verification_result") == "provider_no_result"),
                "pending": sum(1 for r in self._audit_records if not r.get("external_verification_result")),
            },
            "high_confidence_allowed_count": sum(1 for r in self._audit_records if r.get("high_confidence_graph_allowed")),
        }
        summary_path = artifacts_dir / "entity_llm_cleaner_summary.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        paths["entity_llm_cleaner_summary"] = str(summary_path)

        return paths

    def update_verification_status(
        self,
        original_mention: str,
        verification_result: str,
        final_decision: str,
        high_confidence_allowed: bool = False,
        rejection_reason: str | None = None,
    ) -> None:
        """Update verification status for a previously cleaned mention."""
        for record in self._audit_records:
            if record["original_mention"] == original_mention:
                record["external_verification_result"] = verification_result
                record["final_decision"] = final_decision
                record["high_confidence_graph_allowed"] = high_confidence_allowed
                record["rejection_reason"] = rejection_reason
                if verification_result == "unverified":
                    self.suggested_unverified_count += 1
                elif verification_result == "verified":
                    self.external_verified_after_cleaning_count += 1
                break


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

def create_llm_entity_cleaner(
    llm_client: Any = None,
    *,
    enabled: bool = False,
    audit_dir: str | Path | None = None,
) -> LLMEntityCleaner:
    """Create an LLMEntityCleaner instance."""
    return LLMEntityCleaner(llm_client=llm_client, enabled=enabled, audit_dir=audit_dir)
