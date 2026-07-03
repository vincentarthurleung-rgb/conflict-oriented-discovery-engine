"""Describe evidence boundaries without converting absence into negative evidence."""

from __future__ import annotations

from typing import Any


class LimitationReporter:
    def generate(self, bundle: dict[str, Any], card: dict[str, Any]) -> list[str]:
        m = bundle.get("manifest", {})
        limitations: list[str] = []
        if m.get("case_type") == "positive_control_whitebox":
            limitations.append("This is a positive-control white-box case, not a true conflict-discovery case.")
        if "lincs_l1000" in m.get("executed_validators", []):
            limitations.append("LINCS L1000 provides transcriptomic consistency evidence, not direct AMPK phosphorylation validation.")
        interpretation = card.get("validation_summary", {}).get("lincs_interpretation")
        if interpretation == "mixed":
            limitations.append("External validation is mixed, not supportive.")
        unavailable = m.get("recommended_but_unavailable_validators", [])
        if unavailable:
            names = {"chembl": "ChEMBL", "reactome": "Reactome", "enrichr": "Enrichr", "pubmed_post_cutoff": "PubMed post-cutoff", "opentargets": "OpenTargets"}
            display = [names.get(item, item) for item in unavailable]
            limitations.append(f"{', '.join(display[:-1])}, and {display[-1]} were recommended but unavailable." if len(display) > 1 else f"{display[0]} was recommended but unavailable.")
        if m.get("fulltext_confirmation_status") == "not_enabled":
            limitations.append("Full-text confirmation was disabled by case policy because this case has no true graph conflict." if m.get("true_graph_conflict_count", 0) == 0 else "Full-text confirmation was not enabled.")
        return limitations
