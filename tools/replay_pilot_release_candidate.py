#!/usr/bin/env python3
"""Run a frozen, network-disabled SEEN release candidate; never a live pilot."""
from __future__ import annotations
import argparse,json,socket,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from code_engine.corpus.historical_seen import HistoricalSeen
from code_engine.orchestration.pilot_budget import ModelBudget
from code_engine.orchestration.pilot_case import PilotCaseExecutor
from code_engine.orchestration.pilot_replay import FrozenReplayBackend
from code_engine.orchestration.pilot_delivery import case_queue_row
from code_engine.system_b.annotation_schemas.registry import canonical_json

def run(manifest_path:Path,output:Path):
 m=json.loads(manifest_path.read_text())
 if m.get('kind')!='offline_pilot_release_candidate' or m.get('paid_API_authorized') is not False:raise ValueError('offline_release_manifest_required')
 seen=HistoricalSeen(Path(m['historical_registry']),m['historical_root_sha256'])
 output.mkdir(parents=True,exist_ok=True);budgets={}
 for name,config in m['offline_budget_fixtures'].items():budgets[name]=ModelBudget(output/(name+'.sqlite'),config,offline=True)
 cases=[]
 ids=[c['request']['case_id'] for c in m['cases']]
 if len(ids)!=len(set(ids)):raise ValueError('duplicate_attempt_identity')
 for c in m['cases']:
  request=c['request']
  if request['evidence_mode']!='authentic_seen_replay':raise ValueError('offline_runner_forbids_new_pilot')
  budget=budgets[c['budget_key']];backend=FrozenReplayBackend(m['replays'][c['replay_key']],budget.models['fixture'],fail_stage=c.get('offline_failure_stage'),incomplete=c.get('offline_incomplete_core',False))
  package=PilotCaseExecutor(output/'cases',seen,budget,backend).run(request)
  cases.append(package)
 (output/'manual_review_queue.jsonl').write_text(''.join(canonical_json(case_queue_row(p))+'\n' for p in cases))
 summary={'attempts':len(ids),'delivered':len(cases),'case_ids':ids,'terminal_states':{p['case_id']:p['terminal_state'] for p in cases},'hypotheses':sum(len(pair['alignment']['hypotheses']) for p in cases for pair in p['pair_packages']),'paid_API_calls':0,'source_mode':'authentic_SEEN_engineering_replay','budget_ledgers':{k:b.snapshot() for k,b in budgets.items()}}
 (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 return summary

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 attempts=[]
 def deny(*a,**k):attempts.append('blocked');raise RuntimeError('offline_runner_network_forbidden')
 with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(socket,'getaddrinfo',deny),patch.object(socket,'create_connection',deny):summary=run(args.manifest,args.output)
 (args.output/'network_execution.json').write_text(json.dumps({'blocked_network_attempts':attempts,'paid_API_calls':0,'Fresh_Primary':False,'production_Atlas_writes':0},indent=2)+'\n')
 print(json.dumps({k:v for k,v in summary.items() if k!='budget_ledgers'},ensure_ascii=False))
if __name__=='__main__':main()
