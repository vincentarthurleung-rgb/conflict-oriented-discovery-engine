"""Layer 8 report export orchestrator.

The legacy module name is retained for script compatibility. Ranking,
blueprint construction, and markdown rendering live in `src.reporting`.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from typing import Any, Dict, List

from src.reporting.blueprint import build_report_blueprints, build_intervention_blueprint
from src.reporting.markdown import render_markdown_report
from src.reporting.ranking import rank_hypotheses


class CODEAsyncLayer6Engine:
    """Compatibility async facade for the L8 report export pipeline."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.processing_queue = asyncio.Queue()

    async def stream_ingest_hypotheses(self, hypotheses: List[Dict[str, Any]]) -> None:
        """Push validated candidate hypotheses into the ranking queue."""

        for entry in hypotheses:
            await asyncio.sleep(0.02)
            await self.processing_queue.put(entry)
        await self.processing_queue.put(None)

    async def consume_and_rank_processor(self) -> List[Dict[str, Any]]:
        """Consume queue items and delegate deterministic ranking."""

        aggregated_pool = []
        while True:
            hypothesis_node = await self.processing_queue.get()
            if hypothesis_node is None:
                self.processing_queue.task_done()
                break
            aggregated_pool.append(hypothesis_node)
            self.processing_queue.task_done()
        return rank_hypotheses(aggregated_pool)

    def auto_design_intervention_blueprint(self, anchor_gene: str, relation_sign: int, seed_pair: str = "") -> Dict[str, str]:
        """Compatibility wrapper around the neutral blueprint helper."""

        return build_intervention_blueprint(anchor_gene, relation_sign, seed_pair)

    async def render_markdown_report(self, ranked_data: List[Dict[str, Any]]) -> str:
        """Build report blueprints and render markdown."""

        report_md_path = os.path.join(self.output_dir, "CODE_Ranked_Candidate_Report.md")
        legacy_report_md_path = os.path.join(self.output_dir, "CODE_Advisor_Insight_Report.md")
        report_items = build_report_blueprints(ranked_data)
        async with asyncio.Lock():
            rendered_path = render_markdown_report(report_items, report_md_path)
            # Legacy filename retained for backward compatibility with notebooks or old docs.
            shutil.copyfile(rendered_path, legacy_report_md_path)
            return rendered_path
