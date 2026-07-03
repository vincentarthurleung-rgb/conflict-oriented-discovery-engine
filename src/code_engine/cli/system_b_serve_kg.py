"""Serve the local System B KG API and static explorer."""
import argparse
from code_engine.system_b.kg.kg_api import serve

def main():
    p=argparse.ArgumentParser();p.add_argument('--kg-root',required=True);p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8765);a=p.parse_args();print(f'KG frontend available at http://{a.host}:{a.port}/',flush=True)
    try: serve(a.kg_root,a.host,a.port)
    except KeyboardInterrupt: return 0
    return 0
if __name__=='__main__': raise SystemExit(main())
