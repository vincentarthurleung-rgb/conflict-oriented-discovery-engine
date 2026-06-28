"""Lazy compatibility adapter for the existing Layer 6 search."""


def run_legacy_search() -> None:
    from src.pipelines.stage6_l4_beam_search import execute_l4_search_pipeline

    execute_l4_search_pipeline()
