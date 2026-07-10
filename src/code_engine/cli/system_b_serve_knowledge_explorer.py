"""Serve the C.O.D.E. Atlas knowledge explorer."""
import argparse,os
from code_engine.system_b.explorer.explorer_server import serve
def main(argv=None):
    p=argparse.ArgumentParser(description="Serve the C.O.D.E. Atlas knowledge explorer.");p.add_argument("--display-kg-root",required=True);p.add_argument("--review-root");p.add_argument("--host",default="127.0.0.1");p.add_argument("--port",type=int,default=8765);auth=p.add_mutually_exclusive_group();auth.add_argument("--require-auth",dest="require_auth",action="store_true");auth.add_argument("--no-auth",dest="require_auth",action="store_false");p.set_defaults(require_auth=False);p.add_argument("--users-file");p.add_argument("--public-preview",action="store_true");p.add_argument("--allow-registration",action="store_true");p.add_argument("--auth-lockout-seconds",type=int,default=300);p.add_argument("--auth-max-failed-attempts",type=int,default=5);a=p.parse_args(argv)
    def ready():print("CODE_ATLAS_READY",flush=True);print(f"C.O.D.E. Atlas available at http://{a.host}:{a.port}/",flush=True)
    try:
        if a.public_preview and a.host not in {"127.0.0.1","localhost","::1"}:raise ValueError("Public preview must bind to a loopback host and be exposed through a secured reverse proxy or tunnel")
        serve(a.display_kg_root,a.review_root,a.host,a.port,ready,require_auth=a.require_auth or a.public_preview,users_file=a.users_file,secret_key=os.environ.get("ATLAS_SECRET_KEY"),public_preview=a.public_preview,allow_registration=a.allow_registration,max_failed_attempts=a.auth_max_failed_attempts,lockout_seconds=a.auth_lockout_seconds)
    except (OSError,FileNotFoundError,ValueError) as error:print(f"CODE_ATLAS_FAILED: {error}",flush=True);return 1
    except KeyboardInterrupt:return 0
    return 0
if __name__=="__main__":raise SystemExit(main())
