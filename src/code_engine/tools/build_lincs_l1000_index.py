from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.external_data.lincs_l1000 import build_compact_lincs_index


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--dataset",required=True); parser.add_argument("--data-root",type=Path,required=True); parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--perturbagen",required=True); parser.add_argument("--context"); parser.add_argument("--landmark-only",action="store_true"); parser.add_argument("--top-k-genes",type=int,default=50)
    args=parser.parse_args(argv); result=build_compact_lincs_index(dataset=args.dataset,data_root=args.data_root,manifest_path=args.manifest,perturbagen=args.perturbagen,context=args.context,landmark_only=args.landmark_only,top_k_genes=args.top_k_genes)
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
