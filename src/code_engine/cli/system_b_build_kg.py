"""Build a derived System B knowledge graph."""
import argparse
import json
from code_engine.system_b.kg import KGBuilder

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--bundle-root',required=True);parser.add_argument('--output-root',required=True);args=parser.parse_args()
    try: summary=KGBuilder(args.bundle_root,args.output_root).build()
    except (OSError,ValueError,json.JSONDecodeError) as error: print('SYSTEM_B_KG_BUILD_FAIL');print(f'error = {error}');return 1
    print('SYSTEM_B_KG_BUILD_PASS');print(f"case_count = {summary['case_count']}");print(f"node_count = {summary['node_count']}");print(f"edge_count = {summary['edge_count']}");print(f"evidence_count = {summary['evidence_count']}");return 0
if __name__=='__main__': raise SystemExit(main())
