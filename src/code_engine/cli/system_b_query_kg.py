"""Query a locally built System B knowledge graph."""
import argparse,json
from code_engine.system_b.kg import KGQueryEngine

def main():
    p=argparse.ArgumentParser();p.add_argument('--kg-root',required=True);p.add_argument('--entity');p.add_argument('--depth',type=int,default=1);p.add_argument('--triple');p.add_argument('--subject');p.add_argument('--predicate');p.add_argument('--object');p.add_argument('--path-from');p.add_argument('--path-to');p.add_argument('--max-depth',type=int,default=3);p.add_argument('--case-id');a=p.parse_args();q=KGQueryEngine(a.kg_root)
    if a.entity: result=q.get_entity_neighborhood(a.entity,a.depth)
    elif a.triple:
        parts=a.triple.split('|');
        if len(parts)!=3: p.error('--triple must be subject|predicate|object')
        result=q.triple_subgraph(*(part or None for part in parts))
    elif a.subject or a.predicate or a.object: result=q.triple_subgraph(a.subject,a.predicate,a.object)
    elif a.path_from and a.path_to: result={'paths':q.find_paths(a.path_from,a.path_to,a.max_depth)}
    elif a.case_id: result=q.get_case_subgraph(a.case_id)
    else: p.error('specify an entity, triple, path, or case query')
    print('SYSTEM_B_KG_QUERY_PASS');print(json.dumps(result,indent=2,ensure_ascii=False));return 0
if __name__=='__main__': raise SystemExit(main())
