"""Serve the local System B Knowledge Explorer."""
import argparse
from code_engine.system_b.explorer.explorer_server import serve
def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument("--display-kg-root",required=True);p.add_argument("--review-root");p.add_argument("--host",default="127.0.0.1");p.add_argument("--port",type=int,default=8765);a=p.parse_args(argv)
    def ready():print("SYSTEM_B_KNOWLEDGE_EXPLORER_READY",flush=True);print(f"Explorer available at http://{a.host}:{a.port}/",flush=True)
    try:serve(a.display_kg_root,a.review_root,a.host,a.port,ready)
    except (OSError,FileNotFoundError) as error:print(f"SYSTEM_B_KNOWLEDGE_EXPLORER_FAILED: {error}",flush=True);return 1
    except KeyboardInterrupt:return 0
    return 0
if __name__=="__main__":raise SystemExit(main())
