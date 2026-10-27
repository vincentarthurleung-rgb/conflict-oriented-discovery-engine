"""Exhaustive frozen-plan pagination and durable case/source work, no article cap.

Serial defaults are deliberate bounded concurrency (one active request). A page
size is a transport batch, never a selection quota. Access/source gates remain
in the existing prospective acquisition controller injected into the backend.
"""
from __future__ import annotations
import json,sqlite3,time
from pathlib import Path
from contextlib import contextmanager
from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.system_b.annotation_schemas.registry import canonical_json
from code_engine.corpus.historical_seen import SeenBlocked

class ResourcePause(RuntimeError):pass

class PilotCorpus:
 def __init__(self,path:Path,*,seen,client,relevance,acquire,page_size=100,min_interval=0.34,sleep=time.sleep,clock=time.monotonic):
  if type(page_size) is not int or not 1<=page_size<=1000 or min_interval<0:raise ValueError('invalid_transport_controls')
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.seen=seen;self.client=client;self.relevance=relevance;self.acquire=acquire;self.page_size=page_size;self.interval=min_interval;self.sleep=sleep;self.clock=clock;self.last=None
  with self.tx() as d:
   d.executescript('CREATE TABLE IF NOT EXISTS cases(case_id TEXT PRIMARY KEY,request_hash TEXT,payload TEXT);CREATE TABLE IF NOT EXISTS pages(case_id TEXT,query_id TEXT,cursor INTEGER,total INTEGER,done INTEGER,payload TEXT,PRIMARY KEY(case_id,query_id,cursor));CREATE TABLE IF NOT EXISTS papers(paper_key TEXT PRIMARY KEY,metadata TEXT,status TEXT,artifact TEXT,error TEXT);CREATE TABLE IF NOT EXISTS membership(case_id TEXT,paper_key TEXT,decision TEXT,reason TEXT,query_ids TEXT,PRIMARY KEY(case_id,paper_key));CREATE TABLE IF NOT EXISTS resolution(case_id TEXT,query_id TEXT,cursor INTEGER,ordinal INTEGER,paper_key TEXT,decision TEXT,reason TEXT,PRIMARY KEY(case_id,query_id,cursor,ordinal));CREATE TABLE IF NOT EXISTS discovery(case_id TEXT,query_id TEXT,cursor INTEGER,ordinal INTEGER,payload TEXT,PRIMARY KEY(case_id,query_id,cursor,ordinal));')
 @contextmanager
 def tx(self):
  d=sqlite3.connect(self.path,timeout=30);d.row_factory=sqlite3.Row
  try:d.execute('PRAGMA journal_mode=WAL');d.execute('BEGIN IMMEDIATE');yield d;d.commit()
  except BaseException:d.rollback();raise
  finally:d.close()
 def wait(self):
  now=self.clock()
  if self.last is not None:self.sleep(max(0,self.interval-(now-self.last)))
  self.last=self.clock()
 def freeze_case(self,request):
  if request.get('paper_count_limit') is not None:raise ValueError('paper_count_cap_forbidden')
  if not request.get('inclusion_criteria') or not request.get('exclusion_criteria') or not request.get('queries'):raise ValueError('frozen_question_criteria_queries_required')
  cid=request['case_id'];h=content_hash(request)
  with self.tx() as d:
   old=d.execute('SELECT request_hash FROM cases WHERE case_id=?',(cid,)).fetchone()
   if old and old[0]!=h:raise ValueError('case_question_or_search_drift')
   d.execute('INSERT OR IGNORE INTO cases VALUES(?,?,?)',(cid,h,canonical_json(request)))
  return h
 def discover(self,request,*,continue_work=lambda:True):
  self.freeze_case(request);cid=request['case_id']
  for query in request['queries']:
   qid=query['query_id'];cursor=0
   while True:
    with self.tx() as d:old=d.execute('SELECT * FROM pages WHERE case_id=? AND query_id=? AND cursor=?',(cid,qid,cursor)).fetchone()
    if old:
     if old['done']:break
     cursor=json.loads(old['payload'])['next_cursor'];continue
    if not continue_work():raise ResourcePause('retrieval_resource_pause; cursor and remaining queries retained')
    self.wait()
    try:page=self.client.search_page(query,cursor=cursor,page_size=self.page_size)
    except Exception as e:raise ResourcePause('retrieval_interrupted:'+type(e).__name__+':'+str(e)) from e
    records=page['records'];nxt=page.get('next_cursor');total=page['total']
    if type(total) is not int or total<0 or (nxt is not None and (type(nxt) is not int or nxt<=cursor)) or (not records and nxt is not None):raise ResourcePause('invalid_or_stalled_pagination')
    if nxt is None and cursor+len(records)<total:raise ResourcePause('remote_pagination_truncated; not scientific completion')
    # Freeze response before relevance or metadata processing. Retry never loses a page.
    with self.tx() as d:
     d.execute('INSERT INTO pages VALUES(?,?,?,?,?,?)',(cid,qid,cursor,total,nxt is None,canonical_json(page)))
     for ordinal,record in enumerate(records):d.execute('INSERT INTO discovery VALUES(?,?,?,?,?)',(cid,qid,cursor,ordinal,canonical_json(record)))
    if nxt is None:break
    cursor=nxt
  # Metadata rows are idempotent; failed/ineligible and duplicate links persist.
  with self.tx() as d:rows=[dict(x) for x in d.execute('SELECT * FROM discovery WHERE case_id=? ORDER BY query_id,cursor,ordinal',(cid,))]
  for row in rows:
   with self.tx() as d:resolved=d.execute('SELECT 1 FROM resolution WHERE case_id=? AND query_id=? AND cursor=? AND ordinal=?',(cid,row['query_id'],row['cursor'],row['ordinal'])).fetchone()
   if resolved:continue
   raw=json.loads(row['payload']);key=raw.get('pmid') or raw.get('pmcid') or raw.get('doi')
   key='metadata:'+str(key or content_hash(raw))
   with self.tx() as d:already=d.execute('SELECT 1 FROM membership WHERE case_id=? AND paper_key=?',(cid,key)).fetchone()
   if already:
    with self.tx() as d:
     old=d.execute('SELECT query_ids FROM membership WHERE case_id=? AND paper_key=?',(cid,key)).fetchone();queries=sorted(set(json.loads(old[0])+[row['query_id']]))
     d.execute('UPDATE membership SET query_ids=? WHERE case_id=? AND paper_key=?',(canonical_json(queries),cid,key))
     d.execute('INSERT INTO resolution VALUES(?,?,?,?,?,?,?)',(cid,row['query_id'],row['cursor'],row['ordinal'],key,'duplicate','Previously linked exact identity; no new source slot.'))
    continue
   if not continue_work():raise ResourcePause('metadata_resource_pause; discovered records retained')
   meta=raw
   try:
    self.wait();meta=self.client.metadata(raw);identity={k:meta.get(k) for k in ('pmid','pmcid','doi')}
    # One paper may serve multiple current cases. Historical exclusion remains
    # global; the current acquisition is registered under its source work ID.
    identity=self.seen.check_source_identity(identity,case_id='paper:'+str(meta.get('pmid') or meta.get('pmcid')));meta.update(identity)
    key='metadata:'+str(meta.get('pmid') or meta.get('pmcid') or meta.get('doi'));decision=self.relevance(request,meta)
    if decision['eligible'] is True:state,reason='eligible',decision['reason']
    elif decision['eligible'] is False:state,reason='excluded',decision['reason']
    else:state,reason='uncertain',decision['reason']
   except SeenBlocked as e:state,reason=('excluded' if str(e).startswith(('historical_source_excluded','previous_attempt_exposure_excluded')) else 'identity_unresolved'),str(e)
   except Exception as e:state,reason='metadata_failed',type(e).__name__+':'+str(e)
   with self.tx() as d:
    d.execute('INSERT OR IGNORE INTO papers VALUES(?,?,?,NULL,NULL)',(key,canonical_json(meta),'pending'))
    exists=d.execute('SELECT query_ids FROM membership WHERE case_id=? AND paper_key=?',(cid,key)).fetchone()
    if exists:
     d.execute('UPDATE membership SET query_ids=? WHERE case_id=? AND paper_key=?',(canonical_json(sorted(set(json.loads(exists[0])+[row['query_id']]))),cid,key))
    else:d.execute('INSERT INTO membership VALUES(?,?,?,?,?)',(cid,key,state,reason,canonical_json([row['query_id']])))
    d.execute('INSERT INTO resolution VALUES(?,?,?,?,?,?,?)',(cid,row['query_id'],row['cursor'],row['ordinal'],key,'duplicate' if exists else state,reason))
  return self.coverage(cid)
 def download(self,cid,*,continue_work=lambda:True,retry_failed=False):
  # A single writer lease around each download prevents cross-case duplicate
  # downloads. It also bounds download concurrency without an article quota.
  with self.tx() as d:keys=[r[0] for r in d.execute("SELECT paper_key FROM membership WHERE case_id=? AND decision='eligible' ORDER BY paper_key",(cid,))]
  for key in keys:
   if not continue_work():raise ResourcePause('download_resource_pause; remaining sources retained')
   with self.tx() as d:
    paper=d.execute('SELECT * FROM papers WHERE paper_key=?',(key,)).fetchone()
    if paper['status']=='available':
     artifact=json.loads(paper['artifact'])
     if file_hash(Path(artifact['article_path']))!=artifact['source_sha256']:raise ValueError('shared_source_cache_hash_drift')
     continue
    if paper['status'] in ('failed','unavailable','paywalled','ineligible') and not retry_failed:continue
    meta=json.loads(paper['metadata']);identity={k:meta.get(k) for k in ('pmid','pmcid','doi')};work='paper:'+str(meta.get('pmid') or meta.get('pmcid'))
    try:
     self.seen.register_exposure(identity,work);self.wait();artifact=self.acquire(meta)
     if artifact.get('status')!='available':
      d.execute('UPDATE papers SET status=?,artifact=?,error=? WHERE paper_key=?',(artifact.get('status','unavailable'),canonical_json(artifact),artifact.get('reason','access_not_established'),key));continue
     self.seen.check_source(identity,binding={**artifact,'verified_identity':identity,'verification_basis':'NCBI_JATS_identity_binding'},case_id=work)
     d.execute("UPDATE papers SET status='available',artifact=?,error=NULL WHERE paper_key=?",(canonical_json(artifact),key))
    except Exception as e:d.execute("UPDATE papers SET status='failed',error=? WHERE paper_key=?",(type(e).__name__+':'+str(e),key))
  return self.coverage(cid)
 def coverage(self,cid):
  with self.tx() as d:
   request=json.loads(d.execute('SELECT payload FROM cases WHERE case_id=?',(cid,)).fetchone()[0]);pages=[dict(x) for x in d.execute('SELECT * FROM pages WHERE case_id=?',(cid,))]
   rows=[dict(x) for x in d.execute('SELECT m.*,p.status,p.artifact,p.error,p.metadata FROM membership m JOIN papers p USING(paper_key) WHERE case_id=? ORDER BY paper_key',(cid,))]
   discovered=d.execute('SELECT count(*) FROM discovery WHERE case_id=?',(cid,)).fetchone()[0]
   resolved=d.execute('SELECT count(*) FROM resolution WHERE case_id=?',(cid,)).fetchone()[0]
  exhausted=all(any(p['query_id']==q['query_id'] and p['done'] for p in pages) for q in request['queries'])
  unresolved=sum(r['decision'] not in ('eligible','excluded') for r in rows)
  pending=sum(r['decision']=='eligible' and r['status'] in ('pending','failed') for r in rows)
  return {'case_id':cid,'queries':request['queries'],'inclusion_criteria':request['inclusion_criteria'],'exclusion_criteria':request['exclusion_criteria'],'search_exhausted':exhausted,'scientific_completion':False,'membership_decision_semantics':'retrieval_acquisition_eligibility_only_not_scientific_inclusion','retrieved_metadata_rows':discovered,'unique_case_papers':len(rows),'remaining_unprocessed':pending+unresolved+max(0,discovered-resolved),'partial':not exhausted or pending>0 or unresolved>0,'unresolved_metadata_rows':discovered-resolved,'duplicate_metadata_rows':resolved-len(rows),'page_size':self.page_size,'paper_count_limit':None,'max_concurrency':1,'papers':rows,'pages':[{k:p[k] for k in ('query_id','cursor','total','done')} for p in pages]}
 def selected(self,cid):
  with self.tx() as d:rows=[dict(x) for x in d.execute("SELECT p.*,m.query_ids,m.decision,m.reason FROM papers p JOIN membership m USING(paper_key) WHERE m.case_id=? AND m.decision='eligible' AND p.status='available' ORDER BY p.paper_key",(cid,))]
  for r in rows:
   a=json.loads(r['artifact']);meta=json.loads(r['metadata']);yield {'retrieval_eligibility':r['decision'],'retrieval_reason':r['reason'],'query_ids':json.loads(r['query_ids']),'identity':{k:meta[k] for k in ('pmid','pmcid','doi')},'binding':{**a,'verified_identity':{k:meta[k] for k in ('pmid','pmcid','doi')},'verification_basis':'NCBI_JATS_identity_binding'},'article_path':a['article_path'],'handoff':a.get('handoff'),'exposure_work_id':'paper:'+str(meta.get('pmid') or meta.get('pmcid'))}
