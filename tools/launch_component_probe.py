#!/usr/bin/env python3
"""Deterministic repository-local component entrypoint. Controller owns all gates."""
from pathlib import Path
import argparse,hashlib,json,os,runpy,sys,traceback


def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--controller',required=True);parser.add_argument('--binding',required=True)
 parser.add_argument('--output',required=True);parser.add_argument('--execute-probe',action='store_true',required=True)
 args=parser.parse_args();root=Path(__file__).resolve().parents[1];out=Path(args.output).resolve()
 out.mkdir(parents=True,exist_ok=True);terminal=out/'terminal.json';events=[];secrets=[];phase='launcher_startup'
 context={'phase':phase,'live_dispatch_gate_open':False}
 if terminal.exists():raise SystemExit('immutable_terminal_already_exists; use a new revision')
 def guard(event,values):
  if event in ('socket.connect','socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr','socket.sendto'):
   if not context.get('live_dispatch_gate_open',False):
    events.append(event);raise RuntimeError('offline_network_attempt_blocked')
  if event=='open' and values and isinstance(values[0],str) and Path(values[0]).name in ('.env','.env.local'):
   secrets.append('blocked_secret_file_access');raise RuntimeError('offline_secret_access_blocked')
 # Network remains closed until the controller verifies a NEW owner-bound
 # live budget. Offline substitutes never open this gate or inspect secrets.
 sys.addaudithook(guard)
 try:
  if not sys.flags.isolated or sys.flags.no_site:raise ValueError('incorrect_python_environment; require -I with site packages')
  if Path.cwd().resolve()!=root:raise ValueError('unexpected_working_directory; launch from repository root')
  if not (root/'pyproject.toml').is_file() or not (root/'src/code_engine/__init__.py').is_file():raise ValueError('repository_package_missing')
  if not (root/'scripts/search_plan_v24_alpha318a1_source_contracts.py').is_file():raise ValueError('repository_scripts_missing')
  controller=Path(args.controller).resolve();binding=Path(args.binding).resolve()
  if not controller.is_relative_to(root/'runs') or not binding.is_relative_to(root/'runs'):raise ValueError('controller_or_binding_outside_repository_runs')
  # Only the two trusted, discovered repository directories are introduced.
  sys.path[:0]=[str(root),str(root/'src')]
  context={'root':root,'args':args,'network_events':events,'secret_events':secrets,'phase':'controller_import','api_sends':0,'live_dispatch_gate_open':False}
  phase='controller_import'
  namespace=runpy.run_path(str(controller),run_name='component_probe_controller')
  phase='controller_main';result=namespace['main'](context)
  result.update(network_attempts=len(events),real_secret_accesses=len(secrets),actual_API_sends=context['api_sends'])
  if not context['live_dispatch_gate_open'] and (events or secrets or context['api_sends']):raise ValueError('offline_boundary_violated')
  with terminal.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
 except Exception as error:
  failure={'status':'NOT_READY','phase':locals().get('context',{}).get('phase',phase),'reason':type(error).__name__+':'+str(error),'actual_API_sends':context.get('api_sends',0),'network_attempts':len(events),'real_secret_accesses':len(secrets),'dispatch_authorized':False}
  with terminal.open('x') as f:json.dump(failure,f,ensure_ascii=False,indent=2);f.write('\n')
  (out/'failure_traceback.txt').write_text(traceback.format_exc());print(json.dumps(failure),flush=True);return 2
 print(json.dumps(result),flush=True);return 0

if __name__=='__main__':sys.exit(main())
