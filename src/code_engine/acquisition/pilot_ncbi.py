"""Service-limit partitioning, not a corpus quota; frozen predicate union retained."""
from datetime import date,timedelta
from pathlib import Path
import json,time,urllib.parse,urllib.request
from code_engine.acquisition.literature_search import NCBILiteratureClient
from code_engine.acquisition.pilot_corpus import ResourcePause
from code_engine.discovery.ai_review_shadow import content_hash

class PartitionedNCBIClient(NCBILiteratureClient):
 fixture=False
 def __init__(self,state_root,*,execute_authorized=False,sleep=time.sleep):
  self.root=Path(state_root);self.root.mkdir(parents=True,exist_ok=True);self.authorized=execute_authorized;self.sleep=sleep;self.last=0
 def _request(self,params):
  if not self.authorized:raise ResourcePause('new_metadata_acquisition_not_authorized')
  self.sleep(max(0,0.34-(time.monotonic()-self.last)));self.last=time.monotonic()
  url=self.base_url+'/esearch.fcgi?'+urllib.parse.urlencode(params)
  with urllib.request.urlopen(url,timeout=30) as response:raw=response.read()
  value=json.loads(raw);data=value.get('esearchresult') or {}
  if value.get('error') or data.get('ERROR'):raise ResourcePause('remote_esearch_error:'+str(value.get('error') or data['ERROR']))
  return data
 def _count(self,term,source):return int(self._request({'db':source,'term':term,'retmode':'json','retmax':0})['count'])
 def _plan(self,query):
  path=self.root/(content_hash(query)+'.json')
  if path.exists():
   state=json.loads(path.read_text())
   if state.get('sha256')!=content_hash({k:v for k,v in state.items() if k!='sha256'}) or state.get('query')!=query:raise ResourcePause('partition_checkpoint_integrity_failure')
  else:state={'query':query,'pending':[{'term':query['query_string'],'lo':1,'hi':date.max.toordinal()}],'leaves':[],'service_partition_limit':10000}
  source='pmc' if query.get('source')=='pmc' else 'pubmed'
  def save():
   state['sha256']=content_hash({k:v for k,v in state.items() if k!='sha256'});temp=path.with_suffix('.tmp');temp.write_text(json.dumps(state,sort_keys=True));temp.replace(path)
  while state['pending']:
   node=state['pending'][0];count=self._count(node['term'],source)
   if count<=10000:state['leaves'].append({**node,'count':count});state['pending'].pop(0);save();continue
   if node['lo']==node['hi']:save();raise ResourcePause('single_day_or_missing_date_partition_exceeds_remote_service_limit; NOT scientific completion')
   mid=(node['lo']+node['hi'])//2;a=date.fromordinal(node['lo']);b=date.fromordinal(mid)
   qualifier=f'{a.year:04d}/{a.month:02d}/{a.day:02d}:{b.year:04d}/{b.month:02d}/{b.day:02d}[edat]'
   # Complement makes the two children disjoint and exhaustive, including
   # records outside normal date ranges or with missing entry-date indexing.
   children=[{'term':f'({node["term"]}) AND ({qualifier})','lo':node['lo'],'hi':mid},{'term':f'({node["term"]}) NOT ({qualifier})','lo':mid+1,'hi':node['hi']}]
   counts=[self._count(c['term'],source) for c in children]
   if sum(counts)!=count:save();raise ResourcePause('remote_search_snapshot_changed_during_partition; frozen work retained')
   state['pending']=children+state['pending'][1:];save()
  return state
 def search_page(self,query,*,cursor,page_size):
  state=self._plan(query);leaves=state['leaves'];total=sum(n['count'] for n in leaves);base=0
  for leaf in leaves:
   if cursor>=base+leaf['count']:base+=leaf['count'];continue
   local=cursor-base;size=min(page_size,leaf['count']-local);source='pmc' if query.get('source')=='pmc' else 'pubmed'
   data=self._request({'db':source,'term':leaf['term'],'retmode':'json','retstart':local,'retmax':size});ids=data['idlist']
   if int(data['count'])!=leaf['count'] or not ids:raise ResourcePause('remote_partition_changed_or_stalled')
   records=[{'paper_id':('PMC'+str(i)) if source=='pmc' else str(i),'pmid':str(i) if source=='pubmed' else None,'pmcid':'PMC'+str(i) if source=='pmc' else None,'source':source} for i in ids];nxt=cursor+len(ids)
   return {'records':records,'total':total,'next_cursor':nxt if nxt<total else None,'partition_predicate':leaf['term'],'partition_plan_sha256':content_hash(state)}
  return {'records':[],'total':total,'next_cursor':None,'partition_plan_sha256':content_hash(state)}
 def metadata(self,record):
  if not self.authorized:raise ResourcePause('new_metadata_acquisition_not_authorized')
  self.sleep(max(0,0.34-(time.monotonic()-self.last)));self.last=time.monotonic();return super().metadata(record)
