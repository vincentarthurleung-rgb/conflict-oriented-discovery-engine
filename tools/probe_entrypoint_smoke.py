#!/usr/bin/env python3
"""Small reusable REAL-subprocess smoke runner, never an in-process import test."""
from pathlib import Path
import hashlib,json,os,subprocess,sys


def run_smoke(*,repository,controller,binding,output,python=None,extra_python_flags=(),cwd=None,launcher=None):
 root=Path(repository).resolve();out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
 executable=str(Path(python or sys.executable).resolve())
 entry=Path(launcher or root/'tools/launch_component_probe.py').resolve()
 command=[executable,'-I',*extra_python_flags,str(entry),'--controller',str(Path(controller).resolve()),'--binding',str(Path(binding).resolve()),'--output',str(out),'--execute-probe']
 # Deliberately do not pass API credentials, PYTHONPATH, proxy tokens or dotenv.
 environment={k:os.environ[k] for k in ('PATH','LANG','LC_ALL','TZ','TMPDIR') if k in os.environ}
 environment['TZ']='Asia/Shanghai'
 invocation={'argv':command,'cwd':str(Path(cwd or root).resolve()),'environment':environment,'python':executable,'same_startup_for_all_tests':True,'network_and_secret_guards':'installed by exact launcher before repository imports'}
 (out/'subprocess_invocation.json').write_text(json.dumps(invocation,ensure_ascii=False,indent=2)+'\n')
 process=subprocess.run(command,cwd=invocation['cwd'],env=environment,capture_output=True,text=True,timeout=45)
 (out/'subprocess_stdout.txt').write_text(process.stdout);(out/'subprocess_stderr.txt').write_text(process.stderr)
 terminal=json.loads((out/'terminal.json').read_text()) if (out/'terminal.json').is_file() else {'status':'NOT_READY','reason':'child_did_not_write_terminal','actual_API_sends':0}
 return {'exit_code':process.returncode,'terminal':terminal,'invocation':invocation}


if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--controller',required=True);p.add_argument('--binding',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 result=run_smoke(repository=Path(__file__).resolve().parents[1],controller=a.controller,binding=a.binding,output=a.output)
 print(json.dumps(result['terminal'],ensure_ascii=False));sys.exit(result['exit_code'])
