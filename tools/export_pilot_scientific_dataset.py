#!/usr/bin/env python3
"""Reproduce restricted scientific tables from an existing validated case attempt."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from code_engine.orchestration.pilot_dataset import export_attempt_dataset,verify_dataset,atlas_review_records
from code_engine.orchestration.pilot_delivery import validate_case_package
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--atlas-review-export',type=Path);a=p.parse_args()
 if a.output.exists():raise FileExistsError('Dataset exports require a new version directory')
 package=json.loads((a.case_dir/'review_package.json').read_text());validate_case_package(package)
 reviews=atlas_review_records(json.loads(a.atlas_review_export.read_text()),package) if a.atlas_review_export else []
 export_attempt_dataset(package['run_manifest'],a.case_dir,a.output,pairs=package['pair_packages'],human_reviews=reviews);print(json.dumps(verify_dataset(a.output),ensure_ascii=False))
