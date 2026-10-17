"""Consume explicit hash-bound AI review responses; no inference/API execution."""
import argparse
import json
from pathlib import Path

from code_engine.discovery.ai_review_shadow import run_reviewed_pair


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet",type=Path,nargs=2,required=True)
    parser.add_argument("--review",type=Path,nargs=2,required=True)
    parser.add_argument("--core",type=Path,nargs=2)
    parser.add_argument("--prompt",type=Path,required=True)
    parser.add_argument("--output-root",type=Path,required=True)
    args=parser.parse_args()
    receipt=run_reviewed_pair(packet_paths=args.packet,review_paths=args.review,
        core_paths=args.core,prompt_path=args.prompt,output_root=args.output_root)
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
