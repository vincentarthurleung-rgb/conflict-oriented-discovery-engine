"""Export KG summary and alias metadata."""

import json
from pathlib import Path


class KGExporter:
    def __init__(self, root): self.root = Path(root)

    def write_metadata(self, summary, aliases):
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "kg_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        normalized = {key: sorted(value, key=str.lower) for key, value in sorted(aliases.items())}
        (self.root / "kg_entity_aliases.json").write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
