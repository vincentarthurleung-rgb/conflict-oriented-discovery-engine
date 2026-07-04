"""User-facing offline replay from existing L1 artifacts through discovery bundle export."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from code_engine.cli.replay_case_from_stage import replay

def main(argv=None):
    p=argparse.ArgumentParser(description="Replay L2-to-bundle stages without LLM or network access.")
    p.add_argument("--case-id",required=True);p.add_argument("--source-run",type=Path,required=True)
    p.add_argument("--from-stage",choices=("l2","l3","l6","bundle"),default="l2");p.add_argument("--to-stage",choices=("bundle",),default="bundle")
    p.add_argument("--case-version",required=True);p.add_argument("--output-bundle",type=Path,required=True)
    p.add_argument("--no-llm",action="store_true");p.add_argument("--no-network",action="store_true");p.add_argument("--overwrite-bundle",action="store_true")
    a=p.parse_args(argv)
    profile=Path("configs/generated_cases")/a.case_id/"case_profile.json";plan=Path("configs/generated_cases")/a.case_id/"search_plan.frozen.json"
    if not profile.is_file() or not plan.is_file():print(json.dumps({"status":"REPLAY_BLOCKED","error":"generated case profile or frozen plan missing"}));return 2
    expected=a.case_id+"__";suffix=a.output_bundle.name[len(expected):] if a.output_bundle.name.startswith(expected) else a.case_version
    result=replay(profile,plan,a.source_run,a.from_stage,"runs",a.case_version,suffix,no_l1=True,network=False,
        skip_fulltext=True,skip_l7=True,overwrite_bundle=a.overwrite_bundle,bundle_root=a.output_bundle.parent,case_version=a.case_version)
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0

if __name__=="__main__":raise SystemExit(main())
