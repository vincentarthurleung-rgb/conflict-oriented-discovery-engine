"""Exact-input paid-result reuse; uncertain dispatches require reconciliation."""
from contextlib import contextmanager
from pathlib import Path
import fcntl,json,os
from code_engine.discovery.ai_review_shadow import content_hash
from code_engine.orchestration.pilot_budget import BudgetStop
from code_engine.system_b.annotation_schemas.registry import canonical_json

class SourceModelCache:
 def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
 @contextmanager
 def locked(self,key):
  with (self.root/(key+'.lock')).open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX);yield
 def load(self,key):
  p=self.root/(key+'.json')
  if p.exists():
   value=json.loads(p.read_text())
   if value.get('sha256')!=content_hash({k:v for k,v in value.items() if k!='sha256'}):raise BudgetStop('shared_model_cache_hash_drift')
   return value
  if (self.root/(key+'.pending')).exists():raise BudgetStop('unreconciled_prior_dispatch; no duplicate cross-case billing')
 def check_unbound_legacy_dispatches(self):
  # Old keys did not bind a recoverable request body. Never guess that an
  # unknown old dispatch is different from a newly versioned exact request.
  if any(not p.name.startswith('raw_v1_') for p in self.root.glob('*.pending')):
   raise BudgetStop('unreconciled_legacy_dispatch_requires_explicit_reconciliation')
 def capture_raw(self,key,value):
  # Preserve the response before receipt settlement/derivation can fail. This
  # is not a reusable cache hit until settlement succeeds and store() runs.
  self._write(self.root/(key+'.captured'),{**value,'sha256':content_hash(value)})
 def rejected_attempt(self,key):
  # Only a known rejection (currently HTTP 429) can clear dispatch uncertainty.
  (self.root/(key+'.pending')).unlink(missing_ok=True)
 def intent(self,key,case_id,request_id):
  self._write(self.root/(key+'.pending'),{'case_id':case_id,'request_id':request_id})
 def store(self,key,value):
  value={**value,'sha256':content_hash(value)};self._write(self.root/(key+'.json'),value);(self.root/(key+'.pending')).unlink(missing_ok=True)
 def _write(self,p,value):
  tmp=p.with_suffix(p.suffix+'.tmp')
  with tmp.open('w') as f:f.write(canonical_json(value));f.flush();os.fsync(f.fileno())
  os.replace(tmp,p)
