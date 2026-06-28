"""Markdown rendering for L8 report export."""

from __future__ import annotations

import os
from typing import Any, Dict, List


BLOCKED_LEGACY_STATUS_TEXT = (
    "Verified_By_Hardened_Omics_Sign_Locked",
    "Passed_By_General_Fallback",
)


def _clean_status(status: str) -> str:
    replacements = {
        "Verified_By_Hardened_Omics_Sign_Locked": "Legacy_Status_Replaced_By_Validation_Result",
        "Passed_By_General_Fallback": "Unresolved_No_Coverage",
    }
    cleaned = replacements.get(status, status)
    if "truth_locked" in str(cleaned).lower():
        return "Legacy_Status_Replaced_By_Validation_Result"
    return cleaned


def render_markdown_report(report_items: List[Dict[str, Any]], output_path: str) -> str:
    """Render precomputed report items into markdown without changing scores."""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("# C.O.D.E. Layer 8: Ranked Candidate Intervention Report\n")
        handle.write("**Pipeline Base Version**: v4.0-alpha | **Report Export**: deterministic markdown renderer\n\n")
        handle.write("> Validation statuses reflect validator coverage. Curated omics support is not full LINCS validation.\n\n")
        handle.write("---\n\n")

        for item in report_items:
            handle.write(f"### Rank {item['rank']}: {item['hypothesis_id']}\n")
            handle.write(f"* **Core causal seed pair**: `{item['seed_pair']}`\n")
            anchor_source = (
                "legacy_compatibility"
                if item.get("anchor_gene_semantics") == "legacy"
                else item.get("anchor_gene_source", "unresolved")
            )
            handle.write(f"* **Anchor gene**: **{item['anchor_gene']}** (`{anchor_source}`)\n")
            handle.write(f"* **Ranking score**: `{item['global_ranking_score']}`\n")
            handle.write(f"* **Validation status**: `{_clean_status(item['validation_status'])}`\n")
            handle.write(f"* **Coverage status**: `{item.get('coverage_status', 'unresolved_no_coverage')}`\n")
            handle.write(f"* **Dry-lab next action**: `{item.get('dry_lab_next_action', 'manual_review_required')}`\n")
            if item.get("validation_score") is not None:
                handle.write(f"* **Validation score**: `{item['validation_score']}`\n")
            handle.write("\n")

            handle.write("#### Evidence Record Summary\n")
            evidence_records = item.get("evidence_records", [])
            if evidence_records:
                for evidence in evidence_records:
                    handle.write(
                        f"* `{evidence.get('evidence_id', 'N/A')}`: "
                        f"{evidence.get('claim_role', 'background_only')} / "
                        f"{evidence.get('statement_type', 'unknown')} - "
                        f"{evidence.get('quote') or evidence.get('sentence') or 'No grounded quote'}\n"
                    )
            else:
                handle.write("* No first-class evidence record is available.\n")
            handle.write("\n")

            state = item.get("probabilistic_conflict_state", {})
            handle.write("#### Probabilistic Conflict State\n")
            if state:
                handle.write(f"* Classification: `{state.get('classification', 'unresolved')}`\n")
                handle.write(f"* Conflict probability-like weight: `{state.get('p_conflict', 0.0)}`\n")
                handle.write(f"* Context-dependent weight: `{state.get('p_context_dependent', 0.0)}`\n")
                handle.write("* Interpretation: deterministic posterior-like heuristic, not a Bayesian posterior.\n")
            else:
                handle.write("* No uncertainty-aware conflict state is available.\n")
            handle.write("\n")

            hyperedge = item.get("hypothesis_hyperedge", {})
            handle.write("#### Hypothesis Hyperedge View\n")
            handle.write(f"* Entities: `{[entity.get('name') for entity in hyperedge.get('entities', [])]}`\n")
            handle.write(f"* Mechanism path: `{hyperedge.get('mechanism_path', [])}`\n")
            handle.write(f"* Predicted missing links: `{hyperedge.get('predicted_missing_links', [])}`\n\n")

            reasoning = item.get("reasoning_record", {})
            handle.write("#### Bottleneck / Mechanism / Tradeoff\n")
            handle.write(f"* Bottleneck: {reasoning.get('bottleneck', 'unspecified')}\n")
            handle.write(f"* Mechanism: {reasoning.get('mechanism', 'unspecified')}\n")
            handle.write(f"* Tradeoff: {reasoning.get('tradeoff', 'unspecified')}\n\n")

            handle.write("#### Separating Contexts\n")
            if item.get("separating_contexts"):
                for context in item["separating_contexts"]:
                    handle.write(f"* `{context.get('axis', 'latent_context')}`: {context.get('values', [])} ({context.get('directionality', 'unresolved')})\n")
            else:
                handle.write("* No structured separating context was emitted.\n")
            handle.write("\n")

            handle.write("#### Legacy Context Compatibility\n")
            handle.write(f"> ` {', '.join(item.get('minimal_augmented_context_set', []))} `\n\n")

            handle.write("#### Evidence Traceability\n")
            handle.write("| Evidence ID | Source / DOI | Polarity | Evidence Sentence |\n")
            handle.write("| :--- | :--- | :--- | :--- |\n")
            for trace in item.get("whitebox_traceability", []):
                sign_str = "Positive (+1)" if trace.get("relation_sign", 1) > 0 else "Negative (-1)"
                handle.write(
                    f"| `{trace.get('evidence_id', 'N/A')}` | *{trace.get('source_asset', 'N/A')}* ({trace.get('doi', 'N/A')}) | {sign_str} | \"{trace.get('evidence_sentence', '')}\" |\n"
                )
            handle.write("\n")

            metrics = item.get("metrics_breakdown", {})
            handle.write("#### Ranking Components\n")
            handle.write(f"* Complexity: `{metrics.get('complexity', 0.0)}`\n")
            handle.write(f"* Consistency: `{metrics.get('consistency', 0.0)}`\n")
            handle.write(f"* Identifiability: `{metrics.get('identifiability', 0.0)}`\n\n")

            design = item["intervention_blueprint"]
            handle.write("#### Suggested Experiment Blueprint\n")
            handle.write(f"* **Paradigm**: `{design['paradigm']}`\n")
            handle.write(f"* **Design**: {design['method']}\n")
            handle.write(f"* **Guideline**: {design['guideline']}\n\n")

            limitations = item.get("validation_limitations", [])
            if limitations:
                handle.write("#### Validation Limitations\n")
                for limitation in limitations:
                    handle.write(f"* {limitation}\n")
                handle.write("\n")

            ci = item.get("loss_ci_95", [0.0, 0.0])
            handle.write("#### Confidence Interval\n")
            handle.write(f"* Objective loss interval: `[{ci[0]} , {ci[1]}]`\n\n")
            handle.write("---\n\n")

    return output_path
