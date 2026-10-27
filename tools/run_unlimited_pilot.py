#!/usr/bin/env python3
"""Run only a hash-bound owner-authorized pilot; no authorization is implicit."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from code_engine.orchestration.pilot_runtime import run_owner_authorized
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 print(json.dumps(run_owner_authorized(json.loads(a.manifest.read_text()),a.output,ROOT),ensure_ascii=False))
