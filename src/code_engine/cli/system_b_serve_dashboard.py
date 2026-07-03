"""Serve the unified local System B research dashboard."""
import argparse
from code_engine.system_b.dashboard.dashboard_server import serve

def main():
    p=argparse.ArgumentParser();p.add_argument('--system-b-root',required=True);p.add_argument('--kg-root',required=True);p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8765);a=p.parse_args()
    def ready(): print('SYSTEM_B_DASHBOARD_READY',flush=True);print(f'Dashboard available at http://{a.host}:{a.port}/',flush=True)
    try: serve(a.system_b_root,a.kg_root,a.host,a.port,ready)
    except OSError as error: print(f'SYSTEM_B_DASHBOARD_FAILED: {error}',flush=True);return 1
    except KeyboardInterrupt: return 0
    return 0
if __name__=='__main__': raise SystemExit(main())
