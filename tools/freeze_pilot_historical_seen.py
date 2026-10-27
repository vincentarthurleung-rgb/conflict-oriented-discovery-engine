#!/usr/bin/env python3
"""Freeze available historical exclusion surfaces into a dedicated development run."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from code_engine.corpus.historical_seen import freeze_history
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repository',type=Path,default=ROOT);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 v=freeze_history(a.repository,a.output)
 print(json.dumps({'certified':v['certified'],'root_sha256':v['root_sha256'],'files':len(v['file_inventory']),'source_counts':{k:len(x) for k,x in v['source_identity_sets'].items()},'parse_errors':v['coverage']['structured_parse_errors'],'unresolved_captures':v['coverage']['opaque_captures']}))
 raise SystemExit(0 if v['certified'] else 2)
