"""Export a portable source-bound development queue; never publish or run models."""
import argparse
import json
from pathlib import Path
from code_engine.discovery.pilot_acceptance import export_review_package,review_queue_row

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--case-id',required=True);p.add_argument('--packet',nargs=2,type=Path,required=True)
 p.add_argument('--review',nargs=2,type=Path,required=True);p.add_argument('--core',nargs=2,type=Path,required=True)
 p.add_argument('--prompt',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True)
 a=p.parse_args();package=export_review_package(a.case_id,a.packet,a.review,a.core,a.prompt)
 a.output_root.mkdir(parents=True,exist_ok=False)
 (a.output_root/'review_package.json').write_text(json.dumps(package,ensure_ascii=False,indent=2)+'\n')
 (a.output_root/'manual_review_queue.jsonl').write_text(json.dumps(review_queue_row(package),ensure_ascii=False)+'\n')
 print(json.dumps({'package_sha256':package['package_sha256'],'terminal_state':package['terminal_state'],'published':False,'scientific_authorization':False}))
if __name__=='__main__':main()
