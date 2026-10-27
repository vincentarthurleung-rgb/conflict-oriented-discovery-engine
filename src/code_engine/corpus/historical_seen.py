"""Repository-snapshot exclusion union. Identity tracking never authorizes science."""
from __future__ import annotations
import csv,hashlib,json,re,shutil,sqlite3,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
from code_engine.system_b.annotation_schemas.registry import canonical_json
from code_engine.corpus.identity import normalize_doi

class SeenBlocked(ValueError):pass

EXCLUDED_PARTS={'__pycache__','.git','node_modules','synthetic_not_for_atlas','staging','verification','local_engineering_fixtures','independent_execution','scenarios','length_counterexamples','offline_acceptance_example','crash_matrix'}
def excluded(path):
    return (any(x in path.parts for x in ('execution','repairs')) and any('_offline' in p for p in path.parts)) or any(p in EXCLUDED_PARTS or p.endswith('_tmp') or p.startswith('test_') or p.startswith('pytest-') for p in path.parts)

HISTORY_ROOTS=('runs','data','corpus_cache','runs_archive','archived_experiments','batch_runs',
              'case_bundles','case_bundles_preserved','preserved_case_bundles','audit_reports',
              'cleanup_reports','reports','readiness_reports','external_api_smoke_reports',
              'reference_inputs','system_b_inputs','system_b_outputs','system_b_replays',
              'search_plan_reviews','pass_b_primary_evaluator_workspace','logs')

def digest(obj):return hashlib.sha256(canonical_json(obj).encode()).hexdigest()

def hash_file(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def freeze_history(repository:Path,output:Path,progress=None):
    """Read all historical JSON/JSONL/XML/capture identities, inventory all bytes.

    Exclude declared engineering fixture trees, never incomplete acquisition runs.
    Malformed structured ledgers block certification. Raw failed captures remain
    hashed and excluded conservatively; they cannot certify a new source identity.
    """
    repository=Path(repository).resolve();output=Path(output).resolve();roots=[]
    if output.parent.parent!=repository/'runs':raise SeenBlocked('dedicated_current_development_run_required')
    for root in [repository/name for name in HISTORY_ROOTS]:
        if root.exists():roots.append(root)
    if not roots:raise SeenBlocked('historical_roots_missing')
    paths=sorted(p for root in roots for p in root.rglob('*') if p.is_file() and output.parent not in p.parents and not any(x in ('__pycache__','.git','node_modules') for x in p.parts))
    if not paths:raise SeenBlocked('historical_inventory_empty')
    ids={k:set() for k in ('pmid','pmcid','doi','candidate_id','candidate_payload_sha256','untyped_ncbi_uid')};files=[];errors=[];captures=[];dispositions=[];seen_sources=0
    singular={'pmid':'pmid','pubmed_id':'pmid','pmcid':'pmcid','pmc_id':'pmcid','doi':'doi','normalized_doi':'doi','candidate_id':'candidate_id','candidate_identity':'candidate_id','candidate_payload_sha256':'candidate_payload_sha256'}
    lists={'pmids':'pmid','exposed_unique_pmids':'pmid','seen_pmids':'pmid','pmcids':'pmcid','dois':'doi','historical_identity_aliases':'candidate_id','candidate_ids':'candidate_id'}
    def add(kind,value):
        if not isinstance(value,(str,int)) or isinstance(value,bool):return
        s=str(value).strip()
        if kind=='pmid' and not re.fullmatch(r'\d{1,10}',s):return
        if kind=='pmcid':
            if not re.fullmatch(r'PMC\d+',s,re.I):return
            s=s.upper()
        if kind=='doi':
            s=normalize_doi(s)
            if not s or not s.startswith('10.'):return
        if kind=='candidate_payload_sha256' and not re.fullmatch('[0-9a-f]{64}',s):return
        if s:ids[kind].add(s)
    def walk(x,key='',list_member=False):
        nonlocal seen_sources
        if isinstance(x,dict):
            if any(k in x for k in ('pmid','pmcid','doi')):seen_sources+=1
            if {'actor_or_intervention','action','relation_direction','response_or_endpoint','construction_evidence_span'}<=x.keys():ids['candidate_payload_sha256'].add(digest(x))
            for k,v in x.items():
                if k in ('articles','sources') and isinstance(v,dict):
                    for idkey in v:
                        if re.fullmatch('PMC[0-9]+',idkey):add('pmcid',idkey)
                walk(v,k)
        elif isinstance(x,list):
            if key=='idlist':
                for v in x:
                    if isinstance(v,str) and re.fullmatch(r'\d{1,10}',v):ids['untyped_ncbi_uid'].add(v)
            for v in x:walk(v,key,True)
        elif key in singular:add(singular[key],x)
        elif list_member and key in lists:add(lists[key],x)
        elif isinstance(x,str):
            # Exact tagged identifiers only; conservative exposure, never equivalence.
            for match in re.findall(r'\bPMC\d+\b',x,re.I):add('pmcid',match)
            for match in re.findall(r'\bPMID\s*[:=]\s*(\d{1,10})\b',x,re.I):add('pmid',match)
            if key in ('content','utf8') and x.lstrip().startswith(('{','[')):
                try:walk(json.loads(x))
                except ValueError:pass # Model prose is not a structured acquisition ledger.
    for n,p in enumerate(paths,1):
        rel=str(p.relative_to(repository))
        h=hash_file(p)
        files.append({'path':rel,'sha256':h,'bytes':p.stat().st_size})
        error_start=len(errors);capture_start=len(captures)
        raw=p.read_bytes() if p.suffix in ('.json','.jsonl','.xml','.bin','.csv','.tsv') else b''
        try:
            if p.suffix=='.json':walk(json.loads(raw))
            elif p.suffix in ('.csv','.tsv'):
                for row in csv.DictReader(raw.decode().splitlines(),delimiter='\t' if p.suffix=='.tsv' else ','):walk(row)
            elif p.suffix in ('.db','.sqlite'):
                # Read a private copy including WAL; never open historical databases writable.
                with tempfile.TemporaryDirectory() as td:
                    target=Path(td)/p.name;shutil.copyfile(p,target)
                    for tail in ('-wal','-shm'):
                        companion=Path(str(p)+tail)
                        if companion.exists():shutil.copyfile(companion,Path(str(target)+tail))
                    db=sqlite3.connect('file:'+str(target)+'?mode=ro',uri=True)
                    try:
                        for table, in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
                            safe='"'+table.replace('"','""')+'"'
                            names=[r[1] for r in db.execute('PRAGMA table_info('+safe+')')]
                            for row in db.execute('SELECT * FROM '+safe):
                                walk(dict(zip(names,row)))
                                for val in row:
                                    if isinstance(val,str) and val.lstrip().startswith(('{','[')):
                                        try:walk(json.loads(val))
                                        except ValueError:pass
                    finally:db.close()
            elif p.suffix=='.jsonl':
                decoder=json.JSONDecoder();text=raw.decode();position=0
                while position<len(text):
                    while position<len(text) and text[position].isspace():position+=1
                    if position==len(text):break
                    value,position=decoder.raw_decode(text,position);walk(value)
            elif p.suffix in ('.xml','.bin'):
                # XML identifier tags only; no titles, scientific inference or references.
                try:
                    xml=ET.fromstring(raw)
                    for node in xml.findall('.//MedlineCitation/PMID'):add('pmid',node.text or '')
                    for node in xml.findall('.//PubmedArticleData/ArticleIdList/ArticleId'):
                        kind={'pubmed':'pmid','pmc':'pmcid','doi':'doi'}.get(node.get('IdType'))
                        if kind:add(kind,node.text or '')
                    for node in xml.findall('.//front/article-meta/article-id'):
                        kind={'pmid':'pmid','pmcid':'pmcid','doi':'doi'}.get(node.get('pub-id-type'))
                        if kind:add(kind,node.text or '')
                    for node in xml.findall('.//document/infon'):
                        kind=singular.get(node.get('key','').lower())
                        if kind:add(kind,node.text or '')
                except ET.ParseError:
                    if p.suffix=='.xml' and raw.strip():
                        try:walk(json.loads(raw))
                        except (ValueError,UnicodeDecodeError):errors.append({'path':rel,'reason':'unparseable_XML_identity_surface'})
                    elif p.suffix=='.bin':
                        try:walk(json.loads(raw))
                        except (ValueError,UnicodeDecodeError):
                            if raw.strip() and not p.name.startswith('canonical_body-'):
                                # Extract exact closed article-meta tags if body has undefined entities.
                                front=re.search(rb'<article-meta[ >].*?</article-meta>',raw,re.S)
                                if front:
                                    tags=re.findall(rb'<article-id[^>]*pub-id-type=[\"\'](pmid|pmcid|doi)[\"\'][^>]*>([^<]+)</article-id>',front.group(),re.S)
                                    if tags:
                                        for kind,val in tags:add(kind.decode(),val.decode())
                                    else:captures.append({'path':rel,'sha256':h,'disposition':'unresolved_nonempty_capture'})
                                else:captures.append({'path':rel,'sha256':h,'disposition':'unresolved_nonempty_capture'})
        except (ValueError,UnicodeDecodeError,sqlite3.DatabaseError) as exc:errors.append({'path':rel,'reason':'unparseable_structured_history:'+str(exc)[:100]})
        if (len(errors)>error_start or len(captures)>capture_start) and excluded(p.relative_to(repository)):
            dispositions.append({'path':rel,'sha256':h,'reason':'Explicit offline engineering/fault-injection tree; malformed bytes retained. All parseable identities in this tree ARE included conservatively.','parse_findings':errors[error_start:]+captures[capture_start:]})
            del errors[error_start:];del captures[capture_start:]
        if progress and n%5000==0:progress({'files':n,'of':len(paths),'pmids':len(ids['pmid']),'errors':len(errors)})
    # A full exclusion root is certified only over explicit available filesystem scope.
    # Opaque raw captures need dispositions rather than being silently called empty.
    coverage={'roots':[str(p.relative_to(repository)) for p in roots],'historical_file_inventory_complete':True,
              'excluded_current_development_run':str(output.parent.relative_to(repository)),
              'engineering_disposition_rule':sorted(EXCLUDED_PARTS)+['*_tmp','test_*','pytest-*','offline execution/repairs subtrees'],
              'engineering_malformed_dispositions':dispositions,
              'structured_parse_errors':errors,'opaque_captures':captures,'structured_source_rows_examined':seen_sources,
              'scope':'All available historical structured identity surfaces and captures in the inventoried repository roots. Not a claim about absent external histories or undisclosed aliases.',
              'opaque_identity_policy':'Opaque captures are quarantined. Future source admission requires verified PMID+PMCID+DOI binding and must fail if its source lineage intersects an unresolved opaque capture. Unknown linkage cannot establish novelty.'}
    certified=not errors and not captures and bool(ids['pmid']) and bool(ids['candidate_id'])
    value={'schema_version':'repository_historical_seen_exclusion_v1','certified':certified,'coverage':coverage,
           'source_identity_sets':{k:sorted(ids[k]) for k in ('pmid','pmcid','doi','untyped_ncbi_uid')},
           'candidate_tracking':{k:sorted(ids[k]) for k in ('candidate_id','candidate_payload_sha256')},
           'file_inventory':files,'source_policy':'Exclude any known PMID OR PMCID OR normalized DOI. This is conservative exclusion, not canonical equivalence.',
           'candidate_policy':'Track prior candidate IDs/payload hashes separately; absence of a candidate never proves a source new.'}
    value['root_sha256']=digest(value)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:json.dump(value,f,ensure_ascii=False,sort_keys=True);f.write('\n')
    return value

class HistoricalSeen:
    def __init__(self,path:Path,expected_root:str,*,admission_ledger:Path|None=None):
        self.path=Path(path);self.value=json.loads(self.path.read_text());v=self.value
        if v.get('root_sha256')!=expected_root or digest({k:x for k,x in v.items() if k!='root_sha256'})!=expected_root:raise SeenBlocked('historical_root_hash_mismatch')
        if not v.get('certified'):raise SeenBlocked('historical_history_not_certified')
        self.root=expected_root;self.sources={k:set(x) for k,x in v['source_identity_sets'].items()};self.candidates={k:set(x) for k,x in v['candidate_tracking'].items()}
        self.admission_ledger=Path(admission_ledger) if admission_ledger else None
    def _exposure(self,clean,case_id,*,register=False):
        if not self.admission_ledger:
            if register:raise SeenBlocked('persistent_exposure_ledger_required')
            return
        self.admission_ledger.parent.mkdir(parents=True,exist_ok=True)
        db=sqlite3.connect(self.admission_ledger,timeout=30,isolation_level=None)
        try:
            db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS root_binding(root TEXT PRIMARY KEY)')
            roots=[r[0] for r in db.execute('SELECT root FROM root_binding')]
            if roots and roots!=[self.root]:raise SeenBlocked('exposure_registry_root_drift')
            db.execute('INSERT OR IGNORE INTO root_binding VALUES(?)',(self.root,))
            db.execute('CREATE TABLE IF NOT EXISTS exposure(kind TEXT,value TEXT,case_id TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(kind,value))')
            for kind,value in clean.items():
                old=db.execute('SELECT case_id FROM exposure WHERE kind=? AND value=?',(kind,value)).fetchone()
                if old and old[0]!=case_id:raise SeenBlocked('previous_attempt_exposure_excluded:'+kind)
            if register:
                if not case_id:raise SeenBlocked('case_identity_required_for_exposure')
                for kind,value in clean.items():db.execute('INSERT OR IGNORE INTO exposure(kind,value,case_id) VALUES(?,?,?)',(kind,value,case_id))
            db.commit()
        except BaseException:db.rollback();raise
        finally:db.close()
    def check_source_identity(self,identity:dict,*,case_id=None):
        clean={'pmid':str(identity.get('pmid') or ''),'pmcid':str(identity.get('pmcid') or '').upper(),'doi':normalize_doi(identity.get('doi') or '')}
        matches=[k for k,v in clean.items() if v in self.sources[k]]
        if clean['pmid'] in self.sources.get('untyped_ncbi_uid',set()) or clean['pmcid'][3:] in self.sources.get('untyped_ncbi_uid',set()):matches.append('untyped_historical_NCBI_UID')
        if matches:raise SeenBlocked('historical_source_excluded:'+','.join(matches))
        if not all(clean.values()):raise SeenBlocked('source_identity_information_incomplete')
        if not re.fullmatch(r'\d{1,10}',clean['pmid']) or not re.fullmatch(r'PMC\d+',clean['pmcid']) or not re.fullmatch(r'10\.\d{4,9}/\S+',clean['doi']):raise SeenBlocked('invalid_source_identity')
        self._exposure(clean,case_id)
        return clean

    def register_exposure(self,identity,case_id):
        self._exposure(self.check_source_identity(identity,case_id=case_id),case_id,register=True)

    def check_source(self,identity:dict,*,binding:dict,case_id=None):
        clean=self.check_source_identity(identity,case_id=case_id)
        if binding.get('verified_identity')!=clean or not re.fullmatch('[0-9a-f]{64}',binding.get('source_sha256','')) or binding.get('verification_basis') not in ('NCBI_JATS_identity_binding','verified_frozen_source_identity'):
            raise SeenBlocked('unverifiable_acquired_identity_binding')
        # An asserted verified flag or hash alone is insufficient: inspect the exact
        # acquired ArticleJSON bytes and every required bibliographic identifier.
        try:
            raw=Path(binding['article_path']).read_bytes();article=json.loads(raw)
            actual={'pmid':str(article['pmid']),'pmcid':article['pmcid'].upper(),'doi':normalize_doi(article['doi'])}
            if hashlib.sha256(raw).hexdigest()!=binding['source_sha256'] or actual!=clean:raise ValueError('acquired_identity_bytes_mismatch')
        except (KeyError,ValueError,OSError,TypeError) as e:raise SeenBlocked('unverifiable_acquired_identity_binding:'+str(e)) from e
        if self.value['coverage']['opaque_captures']:raise SeenBlocked('unresolved_opaque_historical_exposure')
        return {'historical_root':self.root,'source_identity':clean,'excluded':False}
    def check_candidate(self,candidate_id,payload_hash):
        if not candidate_id or not re.fullmatch('[0-9a-f]{64}',payload_hash):raise SeenBlocked('candidate_identity_incomplete')
        if candidate_id in self.candidates['candidate_id'] or payload_hash in self.candidates['candidate_payload_sha256']:raise SeenBlocked('historical_candidate_excluded')
