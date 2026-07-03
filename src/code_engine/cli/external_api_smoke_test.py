"""Run bounded reachability checks against configured official APIs."""
import argparse, json
from code_engine.validation.external_api_smoke import DEFAULT_VALIDATORS, ExternalAPISmokeTester, load_dotenv, write_smoke_reports

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--registry',required=True);p.add_argument('--output-root',required=True);p.add_argument('--network',action='store_true');p.add_argument('--no-network',action='store_true');p.add_argument('--case-profile');p.add_argument('--validators');p.add_argument('--timeout-seconds',type=float,default=20);p.add_argument('--max-retries',type=int,default=1);p.add_argument('--json',action='store_true');a=p.parse_args(argv)
    if a.network and a.no_network: p.error('--network and --no-network are mutually exclusive')
    load_dotenv(); validators=[x.strip() for x in a.validators.split(',') if x.strip()] if a.validators else list(DEFAULT_VALIDATORS)
    summary=ExternalAPISmokeTester(a.registry,network_enabled=a.network and not a.no_network,timeout_seconds=a.timeout_seconds,max_retries=a.max_retries).run(validators,a.case_profile);write_smoke_reports(summary,a.output_root)
    print('EXTERNAL_API_SMOKE_TEST_COMPLETED')
    if a.json: print(json.dumps(summary,indent=2,ensure_ascii=False))
    else: print(f"api_count = {summary['api_count']}");print(f"reachable_count = {summary['reachable_count']}");print(f"failed_count = {summary['failed_count']}");print(f"skipped_count = {summary['skipped_count']}")
    return 0
if __name__=='__main__': raise SystemExit(main())
