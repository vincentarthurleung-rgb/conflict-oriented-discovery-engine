from __future__ import annotations
import argparse, json
from pathlib import Path
from code_engine.validation.readiness import check_case_readiness, write_readiness_report

def main(argv=None) -> int:
    p=argparse.ArgumentParser(description="Check whether a case can be run safely")
    p.add_argument("--case-profile",type=Path,required=True); p.add_argument("--search-plan-file",type=Path,required=True)
    p.add_argument("--external-data-root",type=Path,default=Path("data/external")); p.add_argument("--output-root",type=Path,default=Path("readiness_reports")); p.add_argument("--no-write",action="store_true")
    p.add_argument("--network",action="store_true")
    a=p.parse_args(argv); report=check_case_readiness(a.case_profile,a.search_plan_file,a.external_data_root,network_allowed=a.network)
    if not a.no_write: write_readiness_report(report,a.output_root)
    print(json.dumps(report,ensure_ascii=False,indent=2)); return 0 if report["ready"] else 2
if __name__ == "__main__": raise SystemExit(main())
