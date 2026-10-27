"""Complete source views and bounded windows; frozen BODY/prompts stay unchanged.

Offsets are Unicode character offsets in an explicitly hashed normalized source
view, never purported byte offsets in raw XML. XML paths bind each region back
to the immutable JATS. Unknown/noncaption content stays pending, not excluded.
"""
from pathlib import Path
import hashlib,json,re,xml.etree.ElementTree as ET
from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.construction.handoff_adapter import validate_construction_document,construction,NORMALIZATION
from scripts import search_plan_v24_alpha318a1_source_contracts as policy

VERSION='complete_source_windows_v1'
def text_hash(text):return hashlib.sha256(text.encode()).hexdigest()

def jats_source_view(path,identity):
 path=Path(path);raw=path.read_bytes();root=ET.fromstring(raw);article_xpath='/article'
 if policy.local(root.tag)=='pmc-articleset':
  articles=[n for n in root if policy.local(n.tag)=='article']
  if len(articles)!=1:raise ValueError('single_JATS_article_required')
  root=articles[0];article_xpath='/pmc-articleset/article[1]'
 if policy.local(root.tag)!='article':raise ValueError('JATS_article_required')
 regions=[];dispositions=[]
 def visit(node,xpath,headings=(),section_path=()):
  tag=policy.local(node.tag)
  if tag=='sec':
   title=policy.first_child(node,'title');heading=policy.normalize_heading(policy.node_text(title)) if title is not None else ''
   if heading in policy.OTHER_EXCLUDED_HEADINGS or node.get('sec-type','').casefold() in {'supplementary-material','references','acknowledgments','funding'}:
    dispositions.append({'xpath':xpath,'status':'excluded','text_sha256':text_hash(policy.node_text(node)),'characters':len(policy.node_text(node)),'reason':'Existing source_contracts OTHER_EXCLUDED_HEADINGS/sec-type rule','rule':'scripts/search_plan_v24_alpha318a1_source_contracts.py:build_construction_document'});return
   headings=(*headings,heading)
  if tag in ('p','caption','abstract','fig','table-wrap'):
   text=policy.node_text(node)
   if text:regions.append({'section_title':' / '.join(headings) or ('Abstract' if tag=='abstract' else 'body'),'text':text,'source_xpath':xpath,'original_element_id':node.get('id'),'section_path':list(section_path),'kind':{'fig':'figure_text','table-wrap':'table_text','caption':'figure_caption'}.get(tag,'paragraph')})
   return
  counts={};sec_ordinal=0
  for child in node:
   name=policy.local(child.tag);counts[name]=counts.get(name,0)+1
   xp=f'{xpath}/{name}[{counts[name]}]'
   if name=='sec':sec_ordinal+=1
   if name=='title':
    dispositions.append({'xpath':xp,'status':'excluded','characters':len(policy.node_text(child)),'text_sha256':text_hash(policy.node_text(child)),'reason':'Existing constructor uses title as section metadata, not evidence paragraph','rule':'scripts/search_plan_v24_alpha318a1_source_contracts.py:build_construction_document'});continue
   if name in ('sec','p','fig','table-wrap','caption','boxed-text','list','list-item','abstract'):
    visit(child,xp,headings,(*section_path,sec_ordinal) if name=='sec' else section_path)
   elif policy.node_text(child):dispositions.append({'xpath':xp,'status':'pending','characters':len(policy.node_text(child)),'text_sha256':text_hash(policy.node_text(child)),'reason':'unsupported_nonparagraph_or_noncaption_text; retained, no scientific exclusion'})
  # Direct text/tails outside recognized paragraphs cannot silently disappear.
  loose=' '.join([node.text or '',*(x.tail or '' for x in node)]).strip()
  if loose:dispositions.append({'xpath':xpath+'/text()','status':'pending','characters':len(loose),'text_sha256':text_hash(loose),'reason':'unstructured_container_text_not_yet_projected'})
 body=next((x for x in root.iter() if policy.local(x.tag)=='body'),None)
 if body is None:raise ValueError('JATS_body_missing')
 meta=next((x for x in root.iter() if policy.local(x.tag)=='article-meta'),None)
 if meta is not None:
  abstracts=[x for x in meta if policy.local(x.tag)=='abstract']
  for i,a in enumerate(abstracts,1):visit(a,f'{article_xpath}/front/article-meta/abstract[{i}]')
 visit(body,article_xpath+'/body')
 xmlsha=hashlib.sha256(raw).hexdigest()
 for i,r in enumerate(regions):
  r.update(section_id='region_'+content_hash([xmlsha,r['source_xpath']])[:24],source_region_id='region_'+content_hash([xmlsha,r['source_xpath']])[:24],paragraph_id='paragraph_'+content_hash([xmlsha,r['source_xpath']])[:24],section_index=i,text_sha256=text_hash(r['text']))
 title=next((policy.node_text(n) for n in root.iter() if policy.local(n.tag)=='article-title'),'')
 return {'title':title,'abstract':'','sections':regions,**identity,'article_type_raw':root.get('article-type'),'source_format':'complete_jats_region_view_v1','original_xml_path':str(path.resolve()),'original_xml_sha256':xmlsha,'normalization':NORMALIZATION,'source_dispositions':dispositions,'scientific_authorization':False}

def plan_windows(article,source_sha256,*,max_chars=16000,overlap_chars=256):
 if not 1<=max_chars<=60000 or not 0<=overlap_chars<max_chars:raise ValueError('invalid_window_bounds')
 sections=list(article['sections'])
 if article.get('abstract'):sections=[{'section_id':'abstract','section_title':'Abstract','text':article['abstract'],'abstract_region':True},*sections]
 windows=[];regions=[]
 for index,sec in enumerate(sections):
  text=sec['text'];sid=sec.get('source_region_id') or content_hash([source_sha256,'abstract' if sec.get('abstract_region') else index-(1 if article.get('abstract') else 0)])
  section_index=None if sec.get('abstract_region') else index-(1 if article.get('abstract') else 0)
  region={'region_id':sid,'section_index':section_index,'section_id':sec.get('section_id'),'section_title':sec.get('section_title',''),'source_xpath':sec.get('source_xpath'),'paragraph_id':sec.get('paragraph_id',sid),'characters':len(text),'text_sha256':text_hash(text),'coordinate_space':'exact_source_ArticleJSON_section_unicode_chars'};regions.append(region)
  start=0
  while start<len(text):
   end=min(len(text),start+max_chars)
   if end<len(text):
    # Prefer actual paragraph/sentence structure, never remove separator text.
    cut=max(text.rfind('\n\n',start+max(max_chars//2,overlap_chars+1),end),text.rfind('. ',start+max(max_chars//2,overlap_chars+1),end))
    if cut>start:end=cut+2
   raw=text[start:end];wid='window_'+content_hash([VERSION,source_sha256,sid,start,end,text_hash(raw)])[:24]
   windows.append({'window_id':wid,'region_id':sid,'section_index':section_index,'section_title':region['section_title'],'source_xpath':region['source_xpath'],'paragraph_id':region['paragraph_id'],'source_char_start':start,'source_char_end':end,'text':raw,'text_sha256':text_hash(raw),'overlap_previous_chars':max(0,windows[-1]['source_char_end']-start) if windows and windows[-1]['region_id']==sid else 0})
   if end==len(text):break
   start=end-overlap_chars
 plan={'version':VERSION,'source_sha256':source_sha256,'max_chars':max_chars,'overlap_chars':overlap_chars,'regions':regions,'windows':windows,'source_dispositions':article.get('source_dispositions',[]),'scientific_extraction_complete':False,'source_scope':'JATS BODY and article-meta abstracts; front/back bibliographic metadata excluded under existing ConstructionEvidenceDocument input contract; images and external supplements not acquired or interpreted'}
 plan['plan_sha256']=content_hash(plan);return plan

def construction_window(window,token):
 if window.get('fragments'):
  paragraphs=[];cursor=0
  for i,f in enumerate(window['fragments'],1):
   text=f['text'];path=[int(window['window_id'][-6:],16),i]
   para={'section_path':path,'section_headings':[f['section_title']],'kind':'paragraph','ordinal':1,'text':text,'start_offset':cursor,'end_offset':cursor+len(text)}
   para['span_id']='spanv1_'+construction.digest([construction.SPAN_VERSION,token,path,1,construction.sha_text(text)])
   paragraphs.append(para);cursor+=len(text)+2
  doc={'schema_version':'ConstructionEvidenceDocumentV1','abstract_text':'','body_text':window['text'],'paragraphs':paragraphs,'article_title_visible':False,'bibliography_visible':False,'normalization':NORMALIZATION}
  validate_construction_document(doc,token);return doc
 text=window['text'];path=[int(window['window_id'][-6:],16)];ordinal=1
 para={'section_path':path,'section_headings':[window['section_title']],'kind':'paragraph','ordinal':ordinal,'text':text,'start_offset':0,'end_offset':len(text)}
 para['span_id']='spanv1_'+construction.digest([construction.SPAN_VERSION,token,path,ordinal,construction.sha_text(text)])
 doc={'schema_version':'ConstructionEvidenceDocumentV1','abstract_text':'','body_text':text,'paragraphs':[para],'article_title_visible':False,'bibliography_visible':False,'normalization':NORMALIZATION}
 # Whitespace normalization of source text belongs to the source view, not a
 # second pass that would shift evidence offsets. Frozen validator checks bytes.
 validate_construction_document(doc,token);return doc

def extraction_block(window,pmcid,pmid):
 if window.get('fragments'):
  parts=[];mapping=[];cursor=0
  for f in window['fragments']:
   block=extraction_block(f,pmcid,pmid);raw=block['text'];start=cursor+block['source_prefix_chars']
   mapping.append({**{k:v for k,v in f.items() if k!='text'},'block_char_start':start,'block_char_end':start+len(f['text'])})
   parts.append(raw);cursor+=len(raw)+2
  return {'block_id':window['window_id'],'text':'\n\n'.join(parts),'section':{'section_title':window['section_title']},'paper_metadata':{'pmcid':pmcid,'pmid':pmid},'source_fragment_map':mapping}
 from code_engine.fulltext.fulltext_l1_extractor import classify_section
 title=window['section_title'];kind=classify_section(title)
 # Prefixes are existing extractor framing, never claimed as source text.
 prefix='LINKED_METHODS: ' if 'method' in title.casefold() and kind=='other' else 'CURRENT_'+kind.upper()+': '
 return {'block_id':window['window_id'],'text':prefix+window['text'],'section':{'section_title':title},'paper_metadata':{'pmcid':pmcid,'pmid':pmid},'source_prefix_chars':len(prefix)}

def mapped_evidence(window,span,*,source_prefix_chars=0):
 a,b=span['char_start']-source_prefix_chars,span['char_end']-source_prefix_chars
 if a<0 or b<a:raise ValueError('evidence_points_into_controller_prefix')
 if window['text'][a:b]!=span['text'] or text_hash(span['text'])!=span['text_hash']:raise ValueError('window_evidence_offset_mismatch')
 return {'evidence_span_id':span['evidence_span_id'],'window_id':window['window_id'],'region_id':window['region_id'],'section_index':window['section_index'],'source_xpath':window['source_xpath'],'paragraph_id':window['paragraph_id'],'char_start':window['source_char_start']+a,'char_end':window['source_char_start']+b,'text':span['text'],'text_hash':span['text_hash'],'coordinate_space':'exact_source_ArticleJSON_section_unicode_chars'}

def coverage(plan,states):
 rows=[]
 for region in plan['regions']:
  item={**region,'stages':{}}
  for stage in ('builder_v4','quality_v2','experimental_v3_core'):
   ranges=sorted((f['source_char_start'],f['source_char_end']) for w in plan['windows'] for f in w.get('fragments',[w]) if f['region_id']==region['region_id'] and states.get(w['window_id'],{}).get(stage,{}).get('status') in (('processed','not_applicable') if stage=='quality_v2' else ('processed',)))
   cursor=0;missing=[]
   for a,b in ranges:
    if a>cursor:missing.append([cursor,a])
    cursor=max(cursor,b)
   if cursor<region['characters']:missing.append([cursor,region['characters']])
   item['stages'][stage]={'unprocessed_intervals':missing,'processed_characters':region['characters']-sum(b-a for a,b in missing)}
  rows.append(item)
 total=sum(r['characters'] for r in rows);pending=[d for d in plan['source_dispositions'] if d['status']=='pending'];processed=sum(r['stages']['experimental_v3_core']['processed_characters'] for r in rows)
 return {'source_sha256':plan['source_sha256'],'plan_sha256':plan['plan_sha256'],'regions':rows,'source_dispositions':plan['source_dispositions'],'window_states':states,'supported_region_characters':total,'segmented_supported_region_percent':100.0 if total else 0.0,'extraction_processed_characters':processed,'extraction_processed_percent':100*processed/total if total else 0.0,'unprojected_source_regions':pending,'source_processing_complete':bool(total) and not pending and all(not st['unprocessed_intervals'] for r in rows for st in r['stages'].values()),'scientific_extraction_complete':False,'authority_label':'AI_PROVISIONAL_NOT_INDEPENDENTLY_VALIDATED'}

def grouped_plan_windows(article,source_sha256,*,max_chars=16000,overlap_chars=256,routing_domain=None):
 """Pack within source headings only when the unchanged V3 preflight permits it.

 Original intervals remain accounted even when a source sentence cannot pass
 the frozen multi-figure/input policy. Such windows are pending, never excluded.
 Planning splits are initial source inputs, not model retries/recovery children.
 """
 from code_engine.fulltext.fulltext_l1_v2 import token_budget_preflight,FulltextTokenBudget
 original=plan_windows(article,source_sha256,max_chars=max_chars,overlap_chars=overlap_chars)
 def grouped(fragments):
  text='\n\n'.join(f['text'] for f in fragments)
  wid='window_'+content_hash(['grouped_source_windows_v2_frozen_preflight',source_sha256,[f['window_id'] for f in fragments],*([routing_domain] if routing_domain is not None else [])])[:24]
  return {'window_id':wid,'section_title':' / '.join(fragments[0]['section_title'].split(' / ')[:2]),'text':text,'text_sha256':text_hash(text),'fragments':fragments,'grouping_basis':'consecutive_shared_source_heading_only_not_experiment_equivalence'}
 def preflight(w):
  if routing_domain is not None:
   from code_engine.domain.extraction_routing import routed_v3_preflight
   return routed_v3_preflight(article,extraction_block(w,article.get('pmcid',''),article.get('pmid','')),question_domain=routing_domain)
  return token_budget_preflight(article,extraction_block(w,article.get('pmcid',''),article.get('pmid','')),FulltextTokenBudget())
 def partition(w):
  check=preflight(grouped([w]))
  if check['preflight_decision']=='execute_as_is':return [w]
  # Preserve exact characters, including whitespace at sentence boundaries.
  cuts=[m.end() for m in re.finditer(r'(?<=[.!?])\s+(?=[A-Z0-9])',w['text'])]
  if not cuts and any('safe_input_budget_exceeded' in x for x in check['preflight_reasons']):
   cuts=[m.end() for m in re.finditer(r'\s+',w['text'])]
  cuts=[x for x in cuts if 0<x<len(w['text'])]
  if not cuts:return [w] # unsplittable evidence remains visible and pending
  cut=min(cuts,key=lambda x:abs(x-len(w['text'])//2));parts=[]
  for a,b in ((0,cut),(cut,len(w['text']))):
   if a==b:continue
   raw=w['text'][a:b];piece={**w,'source_char_start':w['source_char_start']+a,'source_char_end':w['source_char_start']+b,'text':raw,'text_sha256':text_hash(raw)}
   piece['window_id']='fragment_'+content_hash([source_sha256,w['region_id'],piece['source_char_start'],piece['source_char_end'],piece['text_sha256']])[:24]
   parts.extend(partition(piece))
  return parts
 fragments=[part for w in original['windows'] for part in partition(w)]
 groups=[];current=[];key=None
 for fragment in fragments:
  parent=tuple(fragment['section_title'].split(' / ')[:2])
  proposal=grouped([*current,fragment])
  if current and (parent!=key or len(proposal['text'])>max_chars or preflight(proposal)['preflight_decision']!='execute_as_is'):
   groups.append(current);current=[]
  current.append(fragment);key=parent
  if preflight(grouped(current))['preflight_decision']!='execute_as_is':groups.append(current);current=[]
 if current:groups.append(current)
 windows=[]
 for parts in groups:
  w=grouped(parts);w['v3_preflight']=preflight(w);w['v3_dispatch_eligible']=w['v3_preflight']['preflight_decision']=='execute_as_is';windows.append(w)
 result={**original,'version':'grouped_source_windows_v3_domain_design' if routing_domain is not None else 'grouped_source_windows_v2_frozen_preflight','routing_domain':routing_domain,'windows':windows,'original_single_region_windows':len(original['windows']),'blocked_window_ids':[w['window_id'] for w in windows if not w['v3_dispatch_eligible']]}
 result.pop('plan_sha256');result['plan_sha256']=content_hash(result);return result

def mapped_evidence_segments(window,span,*,block=None):
 """Map grouped evidence, splitting cross-region spans without invented offsets.

 A source span may include controller separators/role labels. Retain its parent
 identity and exact block coordinates; emit only actual source intersections.
 """
 if not window.get('fragments'):
  return [mapped_evidence(window,span,source_prefix_chars=(block or {}).get('source_prefix_chars',0))]
 block=block or extraction_block(window,'','')
 a,b=span['char_start'],span['char_end']
 if not 0<=a<b<=len(block['text']) or block['text'][a:b]!=span['text'] or text_hash(span['text'])!=span['text_hash']:
  raise ValueError('window_evidence_offset_mismatch')
 mapped=[]
 for f in block['source_fragment_map']:
  start,end=max(a,f['block_char_start']),min(b,f['block_char_end'])
  if start>=end:continue
  text=block['text'][start:end]
  mapped.append({'evidence_span_id':span['evidence_span_id'],'window_id':window['window_id'],**{k:f[k] for k in ('region_id','section_index','source_xpath','paragraph_id')},'char_start':f['source_char_start']+start-f['block_char_start'],'char_end':f['source_char_start']+end-f['block_char_start'],'text':text,'text_hash':text_hash(text),'parent_block_span':{'char_start':a,'char_end':b,'text_hash':span['text_hash']},'coordinate_space':'exact_source_ArticleJSON_section_unicode_chars'})
 if not mapped:raise ValueError('evidence_points_into_controller_prefix')
 return mapped

def verify_plan_accounting(article,plan):
 """Check actual source intervals, not just counts or declared coverage states."""
 sections=list(article['sections'])
 if article.get('abstract'):sections=[{'text':article['abstract']},*sections]
 rows=[]
 for index,region in enumerate(plan['regions']):
  text=sections[index]['text'];intervals=[]
  if len(text)!=region['characters'] or text_hash(text)!=region['text_sha256']:raise ValueError('plan_region_source_mismatch')
  for w in plan['windows']:
   fragments=w.get('fragments',[w])
   if w.get('fragments') and w['text']!='\n\n'.join(f['text'] for f in fragments):raise ValueError('plan_group_body_mismatch')
   for f in fragments:
    if f['region_id']!=region['region_id']:continue
    a,b=f['source_char_start'],f['source_char_end']
    if not 0<=a<b<=len(text) or text[a:b]!=f['text'] or text_hash(f['text'])!=f['text_sha256']:raise ValueError('plan_fragment_coordinate_mismatch')
    intervals.append((a,b))
  cursor=0
  for a,b in sorted(intervals):
   if a>cursor:raise ValueError('plan_unaccounted_source_interval')
   cursor=max(cursor,b)
  if cursor!=len(text):raise ValueError('plan_unaccounted_source_tail')
  rows.append({'region_id':region['region_id'],'characters':len(text),'accounted_characters':cursor,'intervals':intervals})
 return {'source_regions':len(rows),'source_characters':sum(r['characters'] for r in rows),'accounted_characters':sum(r['accounted_characters'] for r in rows),'accounting_percent':100.0 if rows else 0.0,'regions':rows,'source_dispositions':plan['source_dispositions'],'processing_or_extraction_success_inferred':False}

def aggregate_observations(items):
 """Only exact raw payload AND exact source evidence coordinates deduplicate."""
 unique={}
 for item in items:
  f=item['ExperimentalObservationV3'];semantic={k:v for k,v in f.items() if k in ('statement_role','interpretation_raw','combination_mode_raw')}
  semantic.update(experiment={k:v for k,v in f['experiment'].items() if not k.endswith('_id')},measurement={k:v for k,v in f['measurement'].items() if k!='evidence_span_ids'},observation={k:v for k,v in f['observation'].items() if k!='evidence_span_ids'},interventions=[{k:v for k,v in x.items() if k not in ('intervention_id','evidence_span_ids')} for x in f['interventions']],candidate_relation=f['candidate_relation'])
  key=content_hash([f['provenance']['fulltext_source_hash'],semantic,sorted((x['region_id'],x['char_start'],x['char_end'],x['text_hash']) for x in item['source_evidence'])])
  if key not in unique:unique[key]={**item,'aggregation_identity':key,'window_occurrences':[],'observation_occurrences':[]}
  unique[key]['window_occurrences'].append(item['window_id'])
  unique[key]['observation_occurrences'].append({'observation_id':f['observation_id'],'window_id':item['window_id']})
 return list(unique.values())
