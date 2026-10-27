"""Explicit offline transport transcript; no generation or network capability."""
import json
from pathlib import Path
from code_engine.discovery.ai_review_shadow import content_hash,file_hash

class RecordedProviderTransport:
 fixture=True
 def __init__(self,manifest):self.manifest=manifest;self.calls=[]
 def send(self,provider,body):
  key=content_hash({'provider':provider,'body':body});ref=self.manifest['responses'].get(key)
  if not ref:raise RuntimeError('unrecorded_offline_model_request')
  p=Path(ref['path'])
  if file_hash(p)!=ref['sha256']:raise ValueError('frozen_provider_replay_hash_drift')
  self.calls.append(key);return json.loads(p.read_text())

class PinnedSourceCatalog:
 def __init__(self,manifest):self.manifest=manifest;self.fingerprint=content_hash(manifest)
 def select_sources(self,request):
  for spec in self.manifest['sources']:
   if file_hash(Path(spec['article_path']))!=spec['binding']['source_sha256']:raise ValueError('frozen_source_hash_drift')
  return self.manifest['sources']
 def construction_bundle(self,spec):return None # Explicit local BioC/ArticleJSON engineering adaptation only.
 def coverage(self,cid):return {'case_id':cid,'partial':False,'fixture_inventory_exhausted':True,'search_exhausted':None,'search_execution':'not_run; pinned authentic SEEN source inventory replay only','paper_count_limit':None,'sources':len(self.manifest['sources'])}
