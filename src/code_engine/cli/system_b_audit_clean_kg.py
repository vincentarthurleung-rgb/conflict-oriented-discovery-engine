"""Audit a generated System B clean KG."""
from __future__ import annotations
import argparse, json
from code_engine.system_b.kg_quality_audit import audit_clean_kg

def main(argv=None) -> int:
    p = argparse.ArgumentParser(); p.add_argument("--clean-kg-root", required=True); p.add_argument("--output-root", required=True); p.add_argument("--top-n", type=int, default=50); p.add_argument("--write-csv", action=argparse.BooleanOptionalAction, default=True); p.add_argument("--write-json", action=argparse.BooleanOptionalAction, default=True); p.add_argument("--overwrite", action="store_true")
    a = p.parse_args(argv); print(json.dumps(audit_clean_kg(a.clean_kg_root, a.output_root, top_n=a.top_n, write_csv=a.write_csv, write_json=a.write_json, overwrite=a.overwrite), indent=2, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
