"""Minimal deterministic payload builder for newly acquired raw records."""

import json
import re
from pathlib import Path

from code_engine.preprocessing.chunking import chunk_words


def implementation_status() -> str:
    return "minimal_dynamic_payload_builder"


def build_payloads_for_downloads(downloaded: list[dict], repository_root: str | Path = ".") -> list[dict]:
    root = Path(repository_root)
    chunks = []
    for record in downloaded:
        raw_path = root / record["raw_path"]
        raw = raw_path.read_text(encoding="utf-8")
        if raw_path.suffix == ".json":
            payload = json.loads(raw)
            raw = str(payload.get("abstract") or payload.get("abstract_xml") or "")
        text = " ".join(re.sub(r"<[^>]+>", " ", raw).split())
        paper_id = str(record.get("paper_id") or raw_path.stem)
        paper_chunks = chunk_words(text, 1200) if text else []
        output = {
            "asset_id": paper_id,
            "paragraphs": [{"section": "acquired_text", "text": item} for item in paper_chunks],
        }
        target = root / f"data/interim/weighted_payloads/{paper_id}_payload.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        for index, content in enumerate(paper_chunks):
            chunks.append({"paper_id": paper_id, "chunk_id": f"chunk_{index}", "section": "acquired_text", "content": content})
    return chunks
