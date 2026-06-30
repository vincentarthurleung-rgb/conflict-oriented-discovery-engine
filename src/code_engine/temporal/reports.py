"""Markdown report augmentation for temporal evidence chains."""

from __future__ import annotations

from typing import Any


def render_temporal_evidence_section(timelines: list[dict[str, Any]]) -> list[str]:
    lines = ["## Temporal Evidence Timeline / 冲突时间证据链", ""]
    if not timelines:
        return lines + ["No traceable timeline input was available. Human review remains required.", ""]
    for item in timelines:
        label = item.get("conflict_key") or item.get("conflict_id")
        lines += [f"### Conflict: {label}", "", f"Status: `{item.get('status')}`", "",
                  "- System judgment: `non_decisive`", "- Human review required: `true`",
                  "- This status does not prove that the conflict is fully resolved.", ""]
        source, later = item.get("conflict_source_window") or {}, item.get("later_evidence_window") or {}
        lines += ["Conflict source window:", "", f"- Years: {source.get('start_year')}–{source.get('end_year')}",
                  f"- Papers / entropy: {source.get('paper_count', 0)} / {source.get('entropy', 0)}",
                  f"- Directions: `{source.get('direction_distribution', {})}`", "", "Later evidence window:", "",
                  f"- Years: {later.get('start_year')}–{later.get('end_year')}",
                  f"- Papers / dominant direction: {later.get('paper_count', 0)} / {item.get('later_dominant_direction')}",
                  f"- Directions: `{item.get('later_direction_distribution', {})}`", "",
                  "Evidence timeline:", "", "| Year | Role | Direction | Paper | Evidence Span |", "|---|---|---|---|---|"]
        for evidence in item.get("evidence_timeline", []):
            paper = evidence.get("canonical_paper_id") or evidence.get("paper_id") or evidence.get("doi") or evidence.get("title") or "unknown"
            span = str(evidence.get("evidence_span") or evidence.get("evidence_text") or "missing").replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {evidence.get('year')} | {evidence.get('primary_role')} | {evidence.get('direction')} | {paper} | {span} |")
        lines += ["", "System hypothesis vs later evidence:", "", "| Hypothesis | Later evidence pattern | Comparison | Human review question |", "|---|---|---|---|"]
        for comparison in item.get("hypothesis_vs_later_evidence", []):
            lines.append(f"| {comparison.get('hypothesis_text') or comparison.get('hypothesis_id')} | {item.get('latest_evidence_pattern')} | {comparison.get('comparison_to_later_evidence')} | {comparison.get('human_review_question')} |")
        lines += ["", "Later evidence is candidate explanatory support, not final truth. Human review is required.", ""]
    return lines
