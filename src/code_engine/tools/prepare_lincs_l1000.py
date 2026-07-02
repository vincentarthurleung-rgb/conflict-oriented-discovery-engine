from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.external_data.lincs_l1000 import prepare_lincs_dataset


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--dataset",required=True); parser.add_argument("--data-root",type=Path,required=True)
    parser.add_argument("--manifest",type=Path,required=True); parser.add_argument("--check",action="store_true"); parser.add_argument("--unpack",action="store_true")
    args=parser.parse_args(argv); result=prepare_lincs_dataset(dataset=args.dataset,data_root=args.data_root,manifest_path=args.manifest,check=args.check,unpack=args.unpack)
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result["required_files_present"] else 2
if __name__=="__main__": raise SystemExit(main())
