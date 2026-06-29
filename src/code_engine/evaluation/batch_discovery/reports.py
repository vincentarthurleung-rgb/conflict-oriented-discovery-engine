"""Markdown reporting for batch problem-discovery experiments."""

from pathlib import Path


def render_batch_discovery_report(metrics: dict, path: str | Path) -> Path:
    target = Path(path)
    lines = [
        "# Batch Discovery Evaluation", "",
        "The primary endpoint is automated problem discovery, not hypothesis accuracy.", "",
        f"- Large-scale prompt count: {metrics.get('prompt_count', 0)}",
        f"- Papers processed: {metrics.get('abstract_processed_paper_count', 0)}",
        f"- Abstract claims extracted: {metrics.get('abstract_claim_count', 0)}",
        f"- Conflict candidates discovered: {metrics.get('abstract_conflict_candidate_count', 0)}",
        f"- Confirmed conflicts: {metrics.get('confirmed_conflict_count', 0)}",
        f"- Context-resolved conflicts: {metrics.get('context_resolved_conflict_count', 0)}",
        f"- Valid conflict rate: {metrics.get('valid_conflict_rate')}",
        f"- Actionable conflict rate: {metrics.get('actionable_conflict_rate')}",
        f"- Hypotheses generated: {metrics.get('hypothesis_count', 0)}",
        f"- Traceable hypotheses: {metrics.get('traceable_hypothesis_count', 0)}",
        f"- Full-text grounded hypotheses: {metrics.get('fulltext_grounded_hypothesis_count', 0)}",
        f"- Abstract-only follow-ups: {metrics.get('abstract_only_hypothesis_count', 0)}",
        f"- Unique / duplicate paper hits: {metrics.get('unique_paper_count', 0)} / {metrics.get('duplicate_paper_hit_count', 0)}",
        f"- Abstract L1 cache hits / misses: {metrics.get('abstract_l1_cache_hit_count', 0)} / {metrics.get('abstract_l1_cache_miss_count', 0)}",
        f"- Estimated API calls saved by cache: {metrics.get('estimated_api_calls_saved_by_cache', 0)}",
        f"- Estimated cost: ${metrics.get('estimated_cost_usd', 0.0):.6f}",
        f"- Cost per conflict candidate: {metrics.get('cost_per_conflict_candidate')}",
    ]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


__all__ = ["render_batch_discovery_report"]
