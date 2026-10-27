"""SQLite-serialized, conservative reservations for every pilot model dispatch."""
from __future__ import annotations
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR
import copy,hashlib,json,sqlite3
from pathlib import Path
from code_engine.system_b.annotation_schemas.registry import canonical_json

class BudgetStop(RuntimeError):pass

def cost_nusd(tokens_in:int,tokens_out:int,pricing:dict)->int:
    return int(((Decimal(tokens_in)*Decimal(pricing['input_usd_per_million'])+
                 Decimal(tokens_out)*Decimal(pricing['output_usd_per_million']))*1000).to_integral_value(rounding=ROUND_CEILING))

def money_nusd(value,*,cap=False)->int:
    d=Decimal(str(value))
    if not d.is_finite() or d<0:raise BudgetStop('invalid_financial_cap')
    return int((d*10**9).to_integral_value(rounding=ROUND_FLOOR if cap else ROUND_CEILING))

class ModelBudget:
    def __init__(self,path:Path,config:dict,*,offline:bool):
        config=copy.deepcopy(config)
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.config=config;self.offline=offline
        try:
            if config['kind'] not in ('offline_billing_fixture','owner_authorized_model_budget'):raise BudgetStop('unverified_configuration_kind')
            if not offline:
                if config['kind']!='owner_authorized_model_budget':raise BudgetStop('fixture_cannot_authorize_live_API')
                auth=Path(config['authorization_path']);raw=auth.read_bytes()
                if hashlib.sha256(raw).hexdigest()!=config['authorization_sha256']:raise BudgetStop('authorization_hash_mismatch')
                a=json.loads(raw)
                if a.get('scope')!='pilot_model_spend' or a.get('approved_budget_config_sha256')!=self.pricing_fingerprint(config):raise BudgetStop('owner_authorization_not_bound')
            elif config['kind']!='offline_billing_fixture':raise BudgetStop('offline_mode_requires_fixture_config')
            self.total_cap=money_nusd(config['total_cap_usd'],cap=True);self.case_cap=money_nusd(config['case_cap_usd'],cap=True)
            self.models=config['models']
            if not self.models:raise BudgetStop('missing_model_configuration')
            for key,m in self.models.items():
                if not m['provider'] or not m['model'] or not m['verification_basis']:raise BudgetStop('unverified_model_or_pricing')
                for f in ('input_usd_per_million','output_usd_per_million'):
                    d=Decimal(m[f])
                    if not d.is_finite() or d<0 or (not offline and d==0):raise BudgetStop('unverified_price')
                if type(m['max_input_tokens']) is not int or type(m['max_output_tokens']) is not int or min(m['max_input_tokens'],m['max_output_tokens'])<=0:raise BudgetStop('invalid_token_limits')
                if not offline:
                    proof=Path(m['pricing_proof_path']);raw=proof.read_bytes()
                    if hashlib.sha256(raw).hexdigest()!=m['pricing_proof_sha256']:raise BudgetStop('pricing_proof_hash_mismatch')
                    price=json.loads(raw)['models'][m['model']]
                    if Decimal(str(price['input_ceiling_usd_per_million']))!=Decimal(m['input_usd_per_million']) or Decimal(str(price['output_ceiling_usd_per_million']))!=Decimal(m['output_usd_per_million']):raise BudgetStop('unverified_pricing_configuration')
            if type(config['max_attempts']) is not int or not 1<=config['max_attempts']<=2:raise BudgetStop('invalid_retry_limit')
        except (KeyError,ValueError,TypeError,InvalidOperation,OSError) as e:raise BudgetStop('missing_or_unverified_budget:'+str(e)) from e
        self.fingerprint=self.pricing_fingerprint(config)
        with self.tx() as db:
            db.execute('CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS requests(request_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,logical_id TEXT NOT NULL,attempt INTEGER NOT NULL,model_key TEXT NOT NULL,reserved INTEGER NOT NULL,charged INTEGER,state TEXT NOT NULL,input_tokens INTEGER,output_tokens INTEGER,UNIQUE(case_id,logical_id,attempt))')
            old=db.execute("SELECT value FROM metadata WHERE key='config_hash'").fetchone()
            if old and old[0]!=self.fingerprint:raise BudgetStop('budget_configuration_changed')
            db.execute("INSERT OR IGNORE INTO metadata VALUES('config_hash',?)",(self.fingerprint,))
            db.execute("INSERT OR IGNORE INTO metadata VALUES('blocked','')")
            db.execute('CREATE TABLE IF NOT EXISTS allowances(auth_hash TEXT PRIMARY KEY,payload TEXT NOT NULL)')

    @staticmethod
    def pricing_fingerprint(config):
        return hashlib.sha256(canonical_json({k:v for k,v in config.items() if k not in ('authorization_path','authorization_sha256')}).encode()).hexdigest()

    @contextmanager
    def tx(self):
        db=sqlite3.connect(self.path,timeout=30,isolation_level=None);db.row_factory=sqlite3.Row
        try:
            db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
            yield db;db.commit()
        except BaseException:db.rollback();raise
        finally:db.close()

    def reserve(self,case_id,logical_id,attempt,model_key,input_tokens,output_tokens):
        if not case_id or not logical_id or type(attempt) is not int or not 1<=attempt<=self.config['max_attempts']:raise BudgetStop('retry_limit')
        if model_key not in self.models:raise BudgetStop('unconfigured_model')
        m=self.models[model_key]
        if any(type(x) is not int or x<0 for x in (input_tokens,output_tokens)) or input_tokens>m['max_input_tokens'] or output_tokens>m['max_output_tokens']:raise BudgetStop('token_limit')
        amount=cost_nusd(input_tokens,output_tokens,m)
        rid=hashlib.sha256(canonical_json([case_id,logical_id,attempt]).encode()).hexdigest()
        with self.tx() as db:
            reason=db.execute("SELECT value FROM metadata WHERE key='blocked'").fetchone()[0]
            if reason:raise BudgetStop(reason)
            if db.execute('SELECT 1 FROM requests WHERE request_id=?',(rid,)).fetchone():raise BudgetStop('request_already_reserved_or_dispatched')
            prior=db.execute('SELECT count(*) FROM requests WHERE case_id=? AND logical_id=?',(case_id,logical_id)).fetchone()[0]
            if attempt!=prior+1:raise BudgetStop('retry_sequence')
            total=db.execute('SELECT coalesce(sum(coalesce(charged,reserved)),0) FROM requests').fetchone()[0]
            local=db.execute('SELECT coalesce(sum(coalesce(charged,reserved)),0) FROM requests WHERE case_id=?',(case_id,)).fetchone()[0]
            funding=[json.loads(r[0]) for r in db.execute('SELECT payload FROM allowances')]
            case_cap=self.case_cap+sum(money_nusd(a.get('case_increases_usd',{}).get(case_id,'0'),cap=True) for a in funding)
            total_cap=self.total_cap+sum(money_nusd(a['total_increase_usd'],cap=True) for a in funding)
            if local+amount>case_cap:raise BudgetStop('case_financial_cap')
            if total+amount>total_cap:raise BudgetStop('overall_financial_cap')
            db.execute('INSERT INTO requests VALUES(?,?,?,?,?,?,NULL,?,NULL,NULL)',(rid,case_id,logical_id,attempt,model_key,amount,'RESERVED'))
        return rid

    def dispatch(self,rid):
        with self.tx() as db:
            reason=db.execute("SELECT value FROM metadata WHERE key='blocked'").fetchone()[0]
            if reason:raise BudgetStop(reason)
            if db.execute("UPDATE requests SET state='DISPATCHED' WHERE request_id=? AND state='RESERVED'",(rid,)).rowcount!=1:raise BudgetStop('dispatch_not_new_reservation')

    def settle(self,rid,usage):
        reason=None
        with self.tx() as db:
            row=db.execute('SELECT * FROM requests WHERE request_id=?',(rid,)).fetchone()
            if not row or row['state']!='DISPATCHED':raise BudgetStop('usage_without_dispatch_or_duplicate')
            m=self.models[row['model_key']]
            try:
                i,o=usage['input_tokens'],usage['output_tokens']
                if usage['provider']!=m['provider'] or usage['model']!=m['model'] or type(i) is not int or type(o) is not int or min(i,o)<0 or i>m['max_input_tokens'] or o>m['max_output_tokens']:raise ValueError('usage_identity_or_token_mismatch')
                amount=cost_nusd(i,o,m)
                if amount>row['reserved'] or money_nusd(usage['cost_usd'])!=amount:raise ValueError('unverifiable_or_excess_spend')
            except (KeyError,ValueError,TypeError,InvalidOperation,BudgetStop) as e:reason='UNVERIFIABLE_SPEND:'+str(e)
            if reason:
                db.execute("UPDATE metadata SET value=? WHERE key='blocked'",(reason,))
                db.execute("UPDATE requests SET state='UNVERIFIABLE_SPEND' WHERE request_id=?",(rid,))
            else:db.execute("UPDATE requests SET charged=?,state='SETTLED',input_tokens=?,output_tokens=? WHERE request_id=?",(amount,i,o,rid))
        if reason:raise BudgetStop(reason)

    def snapshot(self,case_id=None):
        with self.tx() as db:
            rows=[dict(r) for r in db.execute('SELECT * FROM requests'+(' WHERE case_id=?' if case_id else '')+' ORDER BY request_id',(case_id,) if case_id else ())]
            blocked=db.execute("SELECT value FROM metadata WHERE key='blocked'").fetchone()[0]
            funding=[json.loads(r[0]) for r in db.execute('SELECT payload FROM allowances')]
        return {'config_sha256':self.fingerprint,'case_id':case_id,'requests':rows,'accounted_nusd':sum(r['charged'] if r['charged'] is not None else r['reserved'] for r in rows),'blocked_reason':blocked,'currency':'USD','fixture_accounting_not_actual_API_spend':self.offline,'funding_tranches':funding}

    def add_authorized_tranche(self,approval:dict):
        """A cap increase is separate, explicit and immutable; never zero usage."""
        if self.offline:
            if approval.get('offline_fixture') is not True:raise BudgetStop('offline_funding_fixture_required')
            a=copy.deepcopy(approval)
        else:
            try:
                raw=Path(approval['artifact_path']).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=approval['sha256']:raise BudgetStop('funding_authorization_hash_mismatch')
                a=json.loads(raw)
            except (KeyError,OSError,ValueError) as e:raise BudgetStop('owner_funding_authorization_required') from e
        if a.get('scope')!='pilot_model_spend_extension' or a.get('budget_config_sha256')!=self.fingerprint:raise BudgetStop('funding_not_bound_to_budget')
        money_nusd(a['total_increase_usd'],cap=True)
        for cid,value in a.get('case_increases_usd',{}).items():
            if not cid:raise BudgetStop('funding_case_identity_required')
            money_nusd(value,cap=True)
        raw=canonical_json(a);key=hashlib.sha256(raw.encode()).hexdigest()
        with self.tx() as db:db.execute('INSERT OR IGNORE INTO allowances VALUES(?,?)',(key,raw))
        return key
