"""Curate, validate, diagnose, and review the generated Case 002 frozen plan."""
import argparse, json
from code_engine.search.case002_plan_review import curate_frozen_plan, diagnose_queries, write_review
from code_engine.validation.external_api_smoke import load_dotenv

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--search-plan-file',required=True);p.add_argument('--output-root',default='search_plan_reviews');p.add_argument('--network-diagnostics',action='store_true');p.add_argument('--timeout-seconds',type=float,default=20);a=p.parse_args(argv);load_dotenv()
    payload=curate_frozen_plan(a.search_plan_file);rows=diagnose_queries(payload,network=a.network_diagnostics,timeout=a.timeout_seconds);review=write_review(payload,rows,a.output_root);print('CASE002_SEARCH_PLAN_REVIEW_COMPLETED');print(json.dumps(review,indent=2,ensure_ascii=False));return 0
if __name__=='__main__': raise SystemExit(main())
