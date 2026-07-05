from __future__ import annotations
import argparse,json,os
from code_engine.extraction.client_factory import diagnose_l1_provider
from code_engine.validation.external_api_smoke import load_dotenv

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument("--scope",choices=("abstract","fulltext"),default="fulltext");p.add_argument("--api",action="store_true");p.add_argument("--network",action="store_true");p.add_argument("--smoke-call",action="store_true")
    a=p.parse_args(argv);load_dotenv();result=diagnose_l1_provider(os.getenv("L1_PROVIDER"),os.getenv("MODEL_NAME"),api_enabled=a.api,network_enabled=a.network)
    result["scope"]=a.scope;result["smoke_call_made"]=False
    if a.smoke_call:result["provider_error"]="smoke_call_not_implemented_use_pipeline_replay"
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result["provider_available"] else 2

if __name__=="__main__":raise SystemExit(main())
