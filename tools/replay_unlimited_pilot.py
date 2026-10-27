#!/usr/bin/env python3
"""Offline proof of concrete-stage integration; never launches the ten new cases."""
import argparse,json,sys,socket
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from code_engine.orchestration.pilot_backend import ExistingStagesBackend
from code_engine.orchestration.pilot_recorded import RecordedProviderTransport,PinnedSourceCatalog
from code_engine.orchestration.pilot_budget import ModelBudget
from code_engine.orchestration.pilot_case import PilotCaseExecutor
from code_engine.orchestration.pilot_delivery import case_review_rows
from code_engine.corpus.historical_seen import HistoricalSeen
from code_engine.system_b.annotation_schemas.registry import canonical_json

def replay(manifest,output):
 if manifest.get('kind')!='explicit_offline_concrete_stage_replay':raise ValueError('offline_manifest_required')
 root=Path(output);root.mkdir(parents=True,exist_ok=True);seen=HistoricalSeen(Path(manifest['historical_registry']),manifest['historical_root_sha256']);budget=ModelBudget(root/'budget.sqlite',manifest['billing_fixture'],offline=True)
 transport=RecordedProviderTransport(manifest['transport']);catalog=PinnedSourceCatalog(manifest['source_inventory']);models=manifest['model_stages'];pricing={k:budget.models[v] for k,v in models.items()}
 backend=ExistingStagesBackend(repository=ROOT,catalog=catalog,transport=transport,pricing=pricing,annotations=manifest['source_annotations']);executor=PilotCaseExecutor(root/'cases',seen,budget,backend);packages=[]
 for case in manifest['cases']:
  if case.get('evidence_mode')!='authentic_seen_replay':raise ValueError('offline_replay_forbids_new_case_acquisition')
  packages.append(executor.run(case))
 rows=[r for p in packages for r in case_review_rows(p)];(root/'manual_review_queue.jsonl').write_text(''.join(canonical_json(r)+'\n' for r in rows));summary={'attempt_ids':[p['case_id'] for p in packages],'terminals':{p['case_id']:p['terminal_state'] for p in packages},'offline_transport_replays':len(transport.calls),'actual_model_API_calls':0,'new_literature_acquired':0,'dataset_versions':{p['case_id']:p['run_manifest']['dataset_export']['dataset_version'] for p in packages},'review_units':len(rows),'budget':budget.snapshot()};(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 def deny(*x,**k):raise RuntimeError('offline_external_network_forbidden')
 with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(socket,'create_connection',deny),patch.object(socket,'getaddrinfo',deny):s=replay(json.loads(a.manifest.read_text()),a.output)
 print(json.dumps({k:v for k,v in s.items() if k!='budget'},ensure_ascii=False))
