"""Flask application for authenticated C.O.D.E. Atlas previews."""
from __future__ import annotations
import logging
import secrets
import hashlib
from functools import wraps
from pathlib import Path
from urllib.parse import parse_qs
from flask import Flask,Response,jsonify,redirect,request,send_from_directory,session,url_for
from werkzeug.security import check_password_hash
from .auth import PUBLIC_REGISTER_ERROR,LoginLimiter,find_usable_invite,hash_password,load_user_store,utc_now_iso,validate_display_name,validate_password_strength,validate_username,write_user_store
from .explorer_api import ExplorerAPI
from code_engine.system_b.persistence.database import create_atlas_engine, database_url as resolve_database_url, session_factory, session_scope, sqlite_health
from code_engine.system_b.persistence.models import Annotation, Assignment, EvaluationProject, ReviewItem, User, UserOnboardingAcknowledgement
from code_engine.system_b.persistence.services.adjudication_service import adjudication_detail, adjudication_queue, submit_adjudication
from code_engine.system_b.persistence.services.assignment_service import create_project_with_assignments, my_assignments, my_batches, my_progress, my_review_items
from code_engine.system_b.persistence.services.auth_service import AuthError, authenticate_user, change_password, complete_password_reset, identity_from_user, load_identity, register_with_invite
from code_engine.system_b.persistence.services.evaluation_service import evaluation_readiness, run_evaluation
from code_engine.system_b.persistence.services.gold_service import freeze_gold, gold_candidates, gold_readiness, supersede_gold
from code_engine.system_b.persistence.services.owner_service import correct_empty_pilot_project_namespace, owner_audit_events, owner_change_role, owner_create_invite, owner_create_user, owner_invite_usage, owner_invites, owner_issue_reset_link, owner_issue_temporary_password, owner_overview, owner_people, owner_pilot_preview, owner_projects, owner_quality_alerts, owner_revoke_sessions, owner_set_invite_enabled, owner_system_state, owner_update_user, owner_users, serialize_user
from code_engine.system_b.annotation_schemas import SchemaValidationError, get_schema, schema_for_item_type
from code_engine.system_b.persistence.services.review_service import StaleAnnotationRevision, annotation_to_dict, import_review_items, metrics as db_metrics, review_item_to_dict, save_annotation
from sqlalchemy import select

LOG=logging.getLogger("code_engine.atlas.security")
WARNING_PUBLIC_PREVIEW_HTTP = (
    "WARNING: --public-preview is enabled but the server is likely running on HTTP. "
    "Secure session cookies require HTTPS. Login and session functionality will not work over HTTP. "
    "Use --no-auth for local testing over HTTP, or configure HTTPS for public-preview."
)
LOGIN_ERROR="用户名或密码错误，或账号不可用。"
ROLE_ALLOWED_MODES={"owner":["pharma","reviewer","developer"],"admin":["pharma","reviewer","developer"],"developer":["pharma","reviewer","developer"],"reviewer":["pharma","reviewer"],"pharma":["pharma"]}
ROLE_WORKSPACES={"owner":["discover","review","library","console","owner"],"admin":["discover","review","library","console"],"developer":["discover","review","library","console"],"reviewer":["discover","review","library"],"pharma":["discover","library"]}
DEBUG_FIELDS={"source_file","source_line","bundle_path","display_priority_score","display_priority_score_v2","priority_score","backing_triple_id","noise_risk_score","chain_noise_risk_score","validator_annotations","validator_details","raw_json","raw","bridge_provenance","fulltext_provenance"}
LOGIN_HTML="""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>C.O.D.E. Atlas Login</title><link rel="stylesheet" href="/style.css"></head><body class="login-page"><main class="login-card"><h1>C.O.D.E. Atlas</h1><h2>Biomedical Evidence &amp; Mechanism Explorer</h2><p>Public preview access is restricted.</p>{error}<form method="post"><input type="hidden" name="csrf_token" value="{csrf}"><label>Username<input name="username" autocomplete="username" required></label><label>Password<input type="password" name="password" autocomplete="current-password" required></label><button class="button" type="submit">Sign in</button></form><p id="registration-link" class="muted" hidden>没有账号？<a href="/register">使用邀请码注册</a></p><script>fetch('/api/registration-config').then(function(r){{return r.json()}}).then(function(x){{if(x.allow_registration)document.getElementById('registration-link').hidden=false}}).catch(function(){{}})</script>{warning}</main></body></html>"""
REGISTER_HTML="""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>C.O.D.E. Atlas Register</title><link rel="stylesheet" href="/style.css"></head><body class="login-page"><main class="login-card"><h1>邀请码注册</h1><h2>C.O.D.E. Atlas</h2><p>注册仅面向收到邀请码的审核人员。注册成功后请返回登录页登录。</p><div id="register-message"></div><form id="register-form"><input type="hidden" name="csrf_token" value="{csrf}"><label>用户名<input name="username" autocomplete="username" minlength="3" maxlength="32" pattern="[A-Za-z0-9_.-]{{3,32}}" required></label><label>显示名<input name="display_name" autocomplete="name" minlength="1" maxlength="80" required></label><label>密码<input type="password" name="password" autocomplete="new-password" minlength="12" required></label><label>确认密码<input type="password" name="confirm_password" autocomplete="new-password" minlength="12" required></label><label>邀请码<input name="invite_code" autocomplete="off" required></label><button class="button" type="submit">注册</button><a class="button-sm" href="/login">返回登录</a></form><script>fetch('/api/registration-config').then(function(r){{return r.json()}}).then(function(x){{if(!x.allow_registration)location.href='/login'}});var invite=new URLSearchParams(location.search).get('invite');if(invite)document.querySelector('[name=invite_code]').value=invite;document.getElementById('register-form').addEventListener('submit',async function(e){{e.preventDefault();var f=e.target,b=f.querySelector('button'),m=document.getElementById('register-message');if(f.password.value!==f.confirm_password.value){{m.innerHTML='<p class="error">注册失败，请检查信息或联系管理员</p>';return}}b.disabled=true;m.textContent='';try{{var r=await fetch('/api/register',{{method:'POST',headers:{{'Content-Type':'application/json','X-CSRF-Token':f.csrf_token.value}},body:JSON.stringify({{username:f.username.value,display_name:f.display_name.value,password:f.password.value,confirm_password:f.confirm_password.value,invite_code:f.invite_code.value}})}});var data=await r.json();if(r.ok){{m.innerHTML='<p class="badge saved-indicator">注册成功，请登录</p>';f.reset()}}else{{m.innerHTML='<p class="error">'+(data.error||'注册失败，请检查信息或联系管理员')+'</p>'}}}}catch(err){{m.innerHTML='<p class="error">注册失败，请检查信息或联系管理员</p>'}}finally{{b.disabled=false}}}})</script></main></body></html>"""

def create_app(display_kg_root,review_root=None,*,require_auth=False,users_file=None,secret_key=None,public_preview=False,allow_registration=False,max_failed_attempts=5,lockout_seconds=300,testing=False,database_url=None,require_database=False,legacy_json_readonly=False):
    if public_preview:require_auth=True
    if public_preview and not secret_key:raise ValueError("ATLAS_SECRET_KEY is required in --public-preview mode")
    db_engine=None;db_factory=None
    if database_url or require_database:
        db_engine=create_atlas_engine(resolve_database_url(database_url));db_factory=session_factory(db_engine)
        health=sqlite_health(db_engine)
        if require_database and health.get("schema_version")!="0008_system_a_ingestion_ledger":raise RuntimeError("Atlas database is not migrated to head")
        if review_root and not legacy_json_readonly:
            with session_scope(db_factory) as dbs:import_review_items(dbs,review_root,namespace="test" if not require_auth else "production")
    if require_auth and not db_factory and (not users_file or not Path(users_file).is_file()):raise FileNotFoundError("Authentication requires an existing --users-file")
    store=load_user_store(users_file) if require_auth and users_file and (not db_factory or legacy_json_readonly) else {"users":{},"invites":[]};users=store["users"];invites=store["invites"];users_file_path=Path(users_file) if users_file else None;api=ExplorerAPI(display_kg_root,review_root);static=Path(__file__).parent/"static"
    app=Flask(__name__,static_folder=None);app.secret_key=secret_key or secrets.token_urlsafe(48);app.config.update(TESTING=testing,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax",SESSION_COOKIE_SECURE=bool(public_preview))
    limiter=LoginLimiter(max_failed_attempts,lockout_seconds);register_limiter=LoginLimiter(max_failed_attempts,lockout_seconds);app.extensions["atlas_api"]=api;app.extensions["atlas_limiter"]=limiter;app.extensions["atlas_register_limiter"]=register_limiter;app.extensions["atlas_db_engine"]=db_engine;app.extensions["atlas_db_factory"]=db_factory
    def db_identity():
        if not db_factory or not require_auth:return None
        with session_scope(db_factory) as dbs:return load_identity(dbs,session.get("atlas_user_id"),session.get("atlas_session_version"))
    def legacy_session_user():return session.get("atlas_user") or None
    def authenticated():
        if not require_auth:return True
        if db_factory and not legacy_json_readonly:return bool(db_identity())
        return bool(legacy_session_user())
    def current_role():
        if not require_auth:return "developer"
        if db_factory and not legacy_json_readonly:
            ident=db_identity() or {}
            return ident.get("role","reviewer")
        user=legacy_session_user() or {}
        return user.get("role","reviewer")
    def allowed_modes_for_role(role):return ROLE_ALLOWED_MODES.get(role,ROLE_ALLOWED_MODES["reviewer"])
    def allowed_workspaces_for_role(role):return ROLE_WORKSPACES.get(role,ROLE_WORKSPACES["reviewer"])
    def can_view_debug():return current_role() in {"owner","admin","developer"}
    def can_use_review():return not require_auth or current_role() in {"owner","admin","developer","reviewer"}
    def can_use_dev():return not require_auth or current_role() in {"owner","admin","developer"}
    def can_use_owner():return require_auth and current_role()=="owner"
    def atlas_namespace():return "production" if require_auth else "test"
    def hash_remote(value):
        if not value:return None
        salt=app.secret_key.encode("utf-8")
        return hashlib.sha256(salt+str(value).encode("utf-8")).hexdigest()
    def current_identity():
        if not require_auth:return {"user_id":"local-dev-user","username":"local_dev","display_name":"Local Developer","role":"developer","authenticated":False}
        if db_factory and not legacy_json_readonly:
            ident=db_identity()
            if ident:return ident
            return {"authenticated":False}
        user=legacy_session_user() or {}
        return {"user_id":user.get("user_id"),"username":user.get("username"),"display_name":user.get("display_name"),"role":user.get("role","reviewer"),"authenticated":True}
    def require_owner_api():
        if not authenticated():return jsonify({"error":"authentication_required"}),401
        if not can_use_owner():return jsonify({"error":"forbidden"}),403
        return None
    def redact_debug(value):
        if can_view_debug():return value
        if isinstance(value,list):return [redact_debug(x) for x in value]
        if isinstance(value,dict):
            if "_raw" in value:return value
            return {k:redact_debug(v) for k,v in value.items() if k not in DEBUG_FIELDS}
        return value
    def csrf():
        if "csrf_token" not in session:session["csrf_token"]=secrets.token_urlsafe(32)
        return session["csrf_token"]
    def page_auth(fn):
        @wraps(fn)
        def wrapped(*a,**kw):
            if not authenticated():return redirect(url_for("login",next=request.path))
            return fn(*a,**kw)
        return wrapped
    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"]="nosniff";response.headers["X-Frame-Options"]="DENY";response.headers["Referrer-Policy"]="no-referrer";response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'";response.headers["Permissions-Policy"]="clipboard-write=(self)"
        if authenticated():response.headers["Cache-Control"]="no-store"
        return response
    @app.route("/healthz")
    def healthz():return jsonify({"status":"ok"})
    @app.route("/login",methods=["GET","POST"])
    def login():
        if not require_auth:return redirect("/")
        error="";token=csrf()
        if request.method=="POST":
            username=request.form.get("username","").strip();remote=request.remote_addr or "unknown"
            if request.form.get("csrf_token")!=token:return Response("CSRF validation failed",403)
            normalized=username.casefold()
            if limiter.locked(remote,normalized):LOG.warning("atlas_auth_locked remote_addr=%s",remote);error=LOGIN_ERROR
            else:
                if db_factory and not legacy_json_readonly:
                    try:
                        with session_scope(db_factory) as dbs:
                            user=authenticate_user(dbs,username=normalized,password=request.form.get("password",""),request_context={"ip_hash":hash_remote(remote),"session_hash":hash_remote(token),"request_id":request.headers.get("X-Request-ID")})
                            user_id=user.user_id
                        limiter.success(remote,normalized);session.clear();session["atlas_user_id"]=user_id;session["atlas_session_version"]=user.session_version;session["csrf_token"]=secrets.token_urlsafe(32);LOG.info("atlas_db_auth_success username=%s",normalized);destination=request.args.get("next") or "/";destination=destination if destination.startswith("/") and not destination.startswith("//") else "/";return redirect(destination)
                    except (AuthError,ValueError):
                        limiter.fail(remote,normalized);LOG.warning("atlas_db_auth_failed username=%s remote_addr=%s",normalized or "<empty>",remote);error=LOGIN_ERROR
                else:
                    user=users.get(normalized);valid=bool(user and user.get("enabled",True) and check_password_hash(user["password_hash"],request.form.get("password","")))
                    if valid:
                        limiter.success(remote,normalized);session.clear();session["atlas_user"]={"user_id":None,"username":normalized,"display_name":user.get("display_name",normalized),"role":user.get("role","reviewer")};session["csrf_token"]=secrets.token_urlsafe(32);user["last_login_at"]=utc_now_iso();user["failed_login_count"]=0;users_file_path and write_user_store(users_file_path,users,invites);LOG.info("atlas_auth_success username=%s",normalized);destination=request.args.get("next") or "/";destination=destination if destination.startswith("/") and not destination.startswith("//") else "/";return redirect(destination)
                limiter.fail(remote,normalized);LOG.warning("atlas_auth_failed username=%s remote_addr=%s",normalized or "<empty>",remote);error=LOGIN_ERROR
        return LOGIN_HTML.format(error=f'<p class="error">{error}</p>' if error else "",csrf=token,warning=f'<p class="badge warn">{WARNING_PUBLIC_PREVIEW_HTTP}</p>' if public_preview and request.scheme=="http" else "")
    @app.route("/logout")
    def logout():return redirect("/login" if require_auth else "/")
    @app.route("/api/logout",methods=["POST"])
    def api_logout():
        if not secrets.compare_digest(request.headers.get("X-CSRF-Token",""),csrf()):return jsonify({"error":"csrf_token_invalid"}),403
        session.clear();return jsonify({"ok":True})
    @app.route("/api/registration-config")
    def registration_config():return jsonify({"allow_registration":bool(require_auth and allow_registration)})
    @app.route("/register")
    def register_page():
        if not require_auth or not allow_registration:return redirect("/login")
        return REGISTER_HTML.format(csrf=csrf())
    @app.route("/api/register",methods=["POST"])
    def api_register():
        if not require_auth or not allow_registration:return jsonify({"error":PUBLIC_REGISTER_ERROR}),403
        if not secrets.compare_digest(request.headers.get("X-CSRF-Token",""),csrf()):return jsonify({"error":"csrf_token_invalid"}),403
        data=request.get_json(silent=True) or {};remote=request.remote_addr or "unknown";raw_username=data.get("username","")
        try:username=validate_username(raw_username)
        except ValueError:username=str(raw_username or "").strip().casefold()[:32] or "<invalid>"
        if register_limiter.locked(remote,username):LOG.warning("atlas_register_locked remote_addr=%s",remote);return jsonify({"error":PUBLIC_REGISTER_ERROR}),429
        try:
            username=validate_username(data.get("username"));display_name=validate_display_name(data.get("display_name"));password=validate_password_strength(data.get("password"))
            if password!=str(data.get("confirm_password") or ""):raise ValueError("password_mismatch")
            if db_factory and not legacy_json_readonly:
                with session_scope(db_factory) as dbs:
                    user=register_with_invite(dbs,username=username,display_name=display_name,password=password,confirm_password=data.get("confirm_password"),invite_code=data.get("invite_code",""),request_context={"ip_hash":hash_remote(remote),"session_hash":hash_remote(csrf()),"request_id":request.headers.get("X-Request-ID")})
                    role=user.role
                register_limiter.success(remote,username);LOG.info("atlas_db_register_success username=%s role=%s",username,role);return jsonify({"ok":True,"message":"注册成功，请登录"}),201
            else:
                if username in users:raise ValueError("duplicate_username")
                invite=find_usable_invite(invites,data.get("invite_code",""))
                if not invite:raise ValueError("invalid_invite")
                role=invite.get("role","reviewer") if invite.get("role") in {"owner","admin","developer","reviewer","pharma"} else "reviewer"
                users[username]={"username":username,"password_hash":hash_password(password),"display_name":display_name,"role":role,"enabled":True,"created_at":utc_now_iso(),"failed_login_count":0}
                invite["uses"]=int(invite.get("uses",0))+1;write_user_store(users_file_path,users,invites);register_limiter.success(remote,username);LOG.info("atlas_register_success username=%s role=%s invite_label=%s",username,role,invite.get("label",""));return jsonify({"ok":True,"message":"注册成功，请登录"}),201
        except Exception as error:
            register_limiter.fail(remote,username);LOG.warning("atlas_register_failed remote_addr=%s reason=%s",remote,type(error).__name__);return jsonify({"error":PUBLIC_REGISTER_ERROR}),400
    @app.route("/api/session")
    def api_session():
        if not authenticated():return jsonify({"error":"authentication_required"}),401
        user=current_identity() if require_auth else None;role=current_role();allowed=allowed_workspaces_for_role(role)
        if user and user.get("must_change_password"):allowed=["discover"]
        payload={"user":user,"csrf_token":csrf(),"auth_required":require_auth,"allowed_modes":allowed_modes_for_role(role),"allowed_workspaces":allowed,"debug_access":can_view_debug(),"registration_enabled":bool(require_auth and allow_registration),"database_enabled":bool(db_factory),"namespace":atlas_namespace(),"must_change_password":bool(user and user.get("must_change_password"))}
        if user:payload.update({"username":user.get("username"),"display_name":user.get("display_name"),"role":role})
        else:payload.update({"username":None,"display_name":None,"role":role})
        return jsonify(payload)
    @app.route("/api/<path:subpath>",methods=["GET","POST"])
    def api_route(subpath):
        if not authenticated():return jsonify({"error":"authentication_required"}),401
        path="/api/"+subpath
        if path=="/api/db/health":
            if not db_engine:return jsonify({"error":"database_not_configured"}),503
            return jsonify(sqlite_health(db_engine))
        ident_for_gate=current_identity()
        if ident_for_gate.get("must_change_password") and path not in {"/api/session","/api/logout","/api/account","/api/account/change-password"} and not path.startswith("/api/password-reset/"):
            return jsonify({"error":"password_change_required"}),403
        if path.startswith("/api/password-reset/"):
            token=path.removeprefix("/api/password-reset/")
            if request.method=="GET":return jsonify({"valid":True})
            body=request.get_json(silent=True) or {}
            with session_scope(db_factory) as dbs:return jsonify(complete_password_reset(dbs,token=token,new_password=body.get("password",""),confirm_password=body.get("confirm_password","")))
        if path=="/api/account":
            ident=current_identity()
            if not ident.get("authenticated"):return jsonify({"error":"authentication_required"}),401
            with session_scope(db_factory) as dbs:
                user=dbs.get(User,ident.get("user_id"))
                return jsonify({"user":serialize_user(dbs,user) if user else None})
        if path=="/api/account/change-password" and request.method=="POST":
            ident=current_identity()
            if not ident.get("authenticated"):return jsonify({"error":"authentication_required"}),401
            body=request.get_json(silent=True) or {}
            with session_scope(db_factory) as dbs:
                result=change_password(dbs,user_id=ident.get("user_id"),current_password=body.get("current_password",""),new_password=body.get("password",""),confirm_password=body.get("confirm_password",""),actor=ident)
            session["atlas_session_version"]=result["session_version"]
            return jsonify(result)
        if path.startswith("/api/guidelines/"):
            schema_id=path.removeprefix("/api/guidelines/")
            try:
                schema=get_schema(schema_id)
            except Exception:
                return jsonify({"error":"schema_not_found"}),404
            return jsonify({"schema_id":schema.schema_id,"instructions_version":schema.instructions_version,"instructions_hash":schema.instructions_hash,"updated_at":"2026-07-11","fields":schema.definition.get("fields",[]),"examples":["Static example: opposite signs alone are not sufficient for true_conflict.","Static example: time maps deterministically to duration for context evaluation."],"title":schema.definition.get("title","")})
        if request.method in {"POST","PUT","DELETE"}:
            if not secrets.compare_digest(request.headers.get("X-CSRF-Token",""),csrf()):return jsonify({"error":"csrf_token_invalid"}),403
        if path.startswith("/api/owner/"):
            denied=require_owner_api()
            if denied:return denied
            body=request.get_json(silent=True) or {}
            ident=current_identity()
            try:
                with session_scope(db_factory) as dbs:
                    if path=="/api/owner/overview":return jsonify(owner_overview(dbs))
                    if path=="/api/owner/users":return jsonify(owner_users(dbs,q=request.args.get("q"),role=request.args.get("role"),enabled=request.args.get("enabled"))) if request.method=="GET" else (jsonify(owner_create_user(dbs,owner=ident,username=body.get("username"),display_name=body.get("display_name"),role=body.get("role"),temporary_password=True)),201)
                    if path.startswith("/api/owner/user/"):
                        tail=path.removeprefix("/api/owner/user/").strip("/")
                        parts=tail.split("/")
                        user_id=parts[0]
                        if len(parts)==1 and request.method=="GET":
                            user=dbs.get(User,user_id);return (jsonify({"user":serialize_user(dbs,user)}) if user else (jsonify({"error":"user_not_found"}),404))
                        action=parts[1] if len(parts)>1 else ""
                        if action=="enable" and request.method=="POST":return jsonify(owner_update_user(dbs,owner=ident,user_id=user_id,enabled=True))
                        if action=="disable" and request.method=="POST":return jsonify(owner_update_user(dbs,owner=ident,user_id=user_id,enabled=False))
                        if action=="change-role" and request.method=="POST":return jsonify(owner_change_role(dbs,owner=ident,user_id=user_id,role=body.get("role")))
                        if action=="revoke-sessions" and request.method=="POST":return jsonify(owner_revoke_sessions(dbs,owner=ident,user_id=user_id))
                        if action=="issue-temporary-password" and request.method=="POST":return jsonify(owner_issue_temporary_password(dbs,owner=ident,user_id=user_id))
                        if action=="issue-password-reset" and request.method=="POST":return jsonify(owner_issue_reset_link(dbs,owner=ident,user_id=user_id,base_url=request.host_url.rstrip("/")))
                        if len(parts)==1 and request.method=="PATCH":return jsonify(owner_update_user(dbs,owner=ident,user_id=user_id,display_name=body.get("display_name")))
                    if path=="/api/owner/invites":return jsonify(owner_invites(dbs)) if request.method=="GET" else (jsonify(owner_create_invite(dbs,owner=ident,label=body.get("label"),role=body.get("role") or body.get("default_role") or "reviewer",max_uses=int(body.get("max_uses") or 1),project_scope=body.get("project_scope") or {},notes=body.get("notes") or "",base_url=request.host_url.rstrip("/"))),201)
                    if path.startswith("/api/owner/invite/"):
                        tail=path.removeprefix("/api/owner/invite/").strip("/")
                        parts=tail.split("/")
                        invite_id=parts[0];action=parts[1] if len(parts)>1 else ""
                        if action=="disable" and request.method=="POST":return jsonify(owner_set_invite_enabled(dbs,owner=ident,invite_id=invite_id,enabled=False))
                        if action=="enable" and request.method=="POST":return jsonify(owner_set_invite_enabled(dbs,owner=ident,invite_id=invite_id,enabled=True))
                        if action=="usage":return jsonify(owner_invite_usage(dbs,invite_id=invite_id))
                    if path=="/api/owner/projects/correct-pilot-namespace" and request.method=="POST":return jsonify(correct_empty_pilot_project_namespace(dbs,owner=ident,project_id=body.get("project_id")))
                    if path=="/api/owner/projects":return jsonify(owner_projects(dbs))
                    if path=="/api/owner/system-state":return jsonify(owner_system_state(dbs,database_path=str(resolve_database_url(database_url or "sqlite:///data/code_atlas.db")).replace("sqlite:///",""),schema_head=sqlite_health(db_engine).get("schema_version") if db_engine else None))
                    if path=="/api/owner/pilot/preview" and request.method=="POST":
                        return jsonify(owner_pilot_preview(dbs,namespace=body.get("namespace") or "pilot",case_ids=body.get("case_ids"),item_types=body.get("item_types"),source_scope=body.get("source_scope"),item_ids=body.get("item_ids"),primary_reviewer_user_id=body.get("primary_reviewer_user_id"),secondary_reviewer_user_id=body.get("secondary_reviewer_user_id"),adjudicator_user_id=body.get("adjudicator_user_id"),batch_size=int(body.get("batch_size") or 20),random_seed=body.get("random_seed")))
                    if path=="/api/owner/pilot/create" and request.method=="POST":
                        preview=owner_pilot_preview(dbs,namespace=body.get("namespace") or "pilot",case_ids=body.get("case_ids"),item_types=body.get("item_types"),source_scope=body.get("source_scope"),item_ids=body.get("item_ids"),primary_reviewer_user_id=body.get("primary_reviewer_user_id"),secondary_reviewer_user_id=body.get("secondary_reviewer_user_id"),adjudicator_user_id=body.get("adjudicator_user_id"),batch_size=int(body.get("batch_size") or 20),random_seed=body.get("random_seed"))
                        if preview.get("blocked"):return jsonify({"error":"pilot_preview_blocked","preview":preview}),422
                        result=create_project_with_assignments(dbs,owner=ident,name=body.get("name") or "Owner-created Pilot",namespace="pilot",annotation_schema_version=body.get("annotation_schema_version") or body.get("guideline_version") or "atlas_annotation_v1",primary_reviewer_user_id=body.get("primary_reviewer_user_id"),secondary_reviewer_user_id=body.get("secondary_reviewer_user_id"),adjudicator_user_id=body.get("adjudicator_user_id"),batch_size=int(body.get("batch_size") or 20),case_ids=body.get("case_ids"),item_ids=preview.get("selected_review_item_ids"))
                        return jsonify({"project":result,"preview":preview}),201
                    if path=="/api/owner/people":return jsonify(owner_people(dbs))
                    if path=="/api/owner/quality":return jsonify(owner_quality_alerts(dbs))
                    if path=="/api/owner/audit":return jsonify(owner_audit_events(dbs,actor=request.args.get("actor"),action=request.args.get("action"),project_id=request.args.get("project_id"),limit=int(request.args.get("limit",200))))
                    if path=="/api/owner/assignments" and request.method=="POST":
                        return jsonify(create_project_with_assignments(dbs,owner=ident,name=body.get("name") or "Atlas Production Evaluation",namespace=body.get("namespace") or "production",annotation_schema_version=body.get("annotation_schema_version") or "atlas_annotation_v1",primary_reviewer_user_id=body.get("primary_reviewer_user_id"),secondary_reviewer_user_id=body.get("secondary_reviewer_user_id"),adjudicator_user_id=body.get("adjudicator_user_id"),batch_size=int(body.get("batch_size") or 50),case_ids=body.get("case_ids"),item_ids=body.get("item_ids"))),201
                    if path=="/api/owner/gold/readiness":return jsonify(gold_readiness(dbs,project_id=request.args.get("project_id") or body.get("project_id")))
                    if path=="/api/owner/gold/candidates":return jsonify({"items":gold_candidates(dbs,project_id=request.args.get("project_id") or body.get("project_id"))})
                    if path=="/api/owner/gold/freeze" and request.method=="POST":return jsonify(freeze_gold(dbs,owner=ident,project_id=body.get("project_id"),confirm=bool(body.get("confirm"))))
                    if path=="/api/owner/gold/supersede" and request.method=="POST":return jsonify(supersede_gold(dbs,owner=ident,project_id=body.get("project_id"),gold_version=int(body.get("gold_version"))))
                    if path=="/api/owner/evaluation/readiness":return jsonify(evaluation_readiness(dbs,project_id=request.args.get("project_id") or body.get("project_id"),gold_version=int(request.args.get("gold_version") or body.get("gold_version") or 0) or None))
                    if path=="/api/owner/evaluation/run" and request.method=="POST":return jsonify(run_evaluation(dbs,owner=ident,project_id=body.get("project_id"),gold_version=int(body.get("gold_version"))))
            except PermissionError as error:return jsonify({"error":str(error)}),403
            except KeyError as error:return jsonify({"error":str(error)}),404
            except (ValueError,TypeError) as error:return jsonify({"error":str(error)}),400
            return jsonify({"error":"not_found"}),404
        if db_factory and not legacy_json_readonly and path.startswith("/api/my/"):
            ident=current_identity()
            if not ident.get("authenticated"):return jsonify({"error":"authentication_required"}),401
            body=request.get_json(silent=True) or {}
            with session_scope(db_factory) as dbs:
                if path=="/api/my/assignments":return jsonify({"items":my_assignments(dbs,user_id=ident.get("user_id"))})
                if path=="/api/my/batches":return jsonify({"items":my_batches(dbs,user_id=ident.get("user_id"))})
                if path=="/api/my/review-items":return jsonify({"items":redact_debug(my_review_items(dbs,user_id=ident.get("user_id")))})
                if path=="/api/my/progress":return jsonify(my_progress(dbs,user_id=ident.get("user_id")))
                if path=="/api/my/onboarding":
                    rows=dbs.execute(select(Assignment,ReviewItem,EvaluationProject).join(ReviewItem,Assignment.review_item_id==ReviewItem.review_item_id).join(EvaluationProject,Assignment.project_id==EvaluationProject.project_id).where(Assignment.reviewer_user_id==ident.get("user_id"))).all()
                    items=[];seen=set()
                    for assignment,item,project in rows:
                        schema=schema_for_item_type(item.item_type)
                        if not schema:continue
                        key=(project.project_id,schema.schema_id,schema.instructions_hash)
                        if key in seen:continue
                        seen.add(key)
                        ack=dbs.execute(select(UserOnboardingAcknowledgement).where(UserOnboardingAcknowledgement.user_id==ident.get("user_id"),UserOnboardingAcknowledgement.project_id==project.project_id,UserOnboardingAcknowledgement.schema_id==schema.schema_id,UserOnboardingAcknowledgement.instructions_hash==schema.instructions_hash)).scalar_one_or_none()
                        items.append({"project_id":project.project_id,"project_name":project.name,"namespace":project.namespace,"schema_id":schema.schema_id,"instructions_version":schema.instructions_version,"instructions_hash":schema.instructions_hash,"acknowledged":bool(ack),"acknowledged_at":ack.acknowledged_at.isoformat() if ack else ""})
                    return jsonify({"items":items,"required":any(not x["acknowledged"] and x["namespace"]=="pilot" for x in items)})
                if path=="/api/my/onboarding/acknowledge" and request.method=="POST":
                    schema=get_schema(body.get("schema_id") or "claim_review_v1")
                    existing=dbs.execute(select(UserOnboardingAcknowledgement).where(UserOnboardingAcknowledgement.user_id==ident.get("user_id"),UserOnboardingAcknowledgement.project_id==body.get("project_id"),UserOnboardingAcknowledgement.schema_id==schema.schema_id,UserOnboardingAcknowledgement.instructions_hash==schema.instructions_hash)).scalar_one_or_none()
                    if not existing:
                        dbs.add(UserOnboardingAcknowledgement(user_id=ident.get("user_id"),project_id=body.get("project_id"),schema_id=schema.schema_id,instructions_version=schema.instructions_version,instructions_hash=schema.instructions_hash))
                    return jsonify({"ok":True})
            return jsonify({"error":"not_found"}),404
        if db_factory and not legacy_json_readonly and path.startswith("/api/adjudication"):
            ident=current_identity()
            if ident.get("role") not in {"owner","reviewer"}:return jsonify({"error":"forbidden"}),403
            body=request.get_json(silent=True) or {}
            try:
                with session_scope(db_factory) as dbs:
                    if path=="/api/adjudication/queue":return jsonify({"items":adjudication_queue(dbs,identity=ident,project_id=request.args.get("project_id"))})
                    review_item_id=path.removeprefix("/api/adjudication/").strip("/")
                    project_id=request.args.get("project_id") or body.get("project_id")
                    if request.method=="GET":return jsonify(adjudication_detail(dbs,identity=ident,project_id=project_id,review_item_id=review_item_id))
                    if request.method=="POST":return jsonify(submit_adjudication(dbs,identity=ident,project_id=project_id,review_item_id=review_item_id,payload=body,request_context={"request_id":request.headers.get("X-Request-ID"),"ip_hash":hash_remote(request.remote_addr),"session_hash":hash_remote(session.get("csrf_token"))}))
            except StaleAnnotationRevision as error:return jsonify({"error":str(error)}),409
            except PermissionError as error:return jsonify({"error":str(error)}),403
            except (ValueError,KeyError,TypeError) as error:return jsonify({"error":str(error)}),400
        if path.startswith(("/api/review","/api/annotation","/api/annotations")) and not can_use_review():return jsonify({"error":"forbidden"}),403
        if db_factory and not legacy_json_readonly:
            if require_auth and path=="/api/review-items" and request.method=="GET":
                ident=current_identity()
                with session_scope(db_factory) as dbs:return jsonify({"items":redact_debug(my_review_items(dbs,user_id=ident.get("user_id"))),"total":len(my_review_items(dbs,user_id=ident.get("user_id")))})
            if require_auth and path.startswith("/api/review-item/") and request.method=="GET":
                ident=current_identity()
                item_id=path.removeprefix("/api/review-item/")
                with session_scope(db_factory) as dbs:
                    row=dbs.execute(select(Assignment,ReviewItem).join(ReviewItem,Assignment.review_item_id==ReviewItem.review_item_id).where(Assignment.reviewer_user_id==ident.get("user_id"),Assignment.review_item_id==item_id)).first()
                    if not row:return jsonify({"error":"review_item_not_found"}),404
                    assignment,item=row
                    annotation=dbs.execute(select(Annotation).where(Annotation.project_id==assignment.project_id,Annotation.review_item_id==item.review_item_id,Annotation.reviewer_user_id==ident.get("user_id"))).scalar_one_or_none()
                    project=dbs.get(EvaluationProject,assignment.project_id)
                    return jsonify(redact_debug(review_item_to_dict(item,annotation,assignment=assignment,project=project))),200
            if path.startswith("/api/annotation/") and request.method=="POST":
                item_id=path.removeprefix("/api/annotation/")
                try:
                    with session_scope(db_factory) as dbs:
                        value=save_annotation(dbs,review_item_id=item_id,payload=request.get_json(silent=True) or {},identity=current_identity(),namespace=atlas_namespace(),request_id=request.headers.get("X-Request-ID"),ip_hash=hash_remote(request.remote_addr),session_hash=hash_remote(session.sid if hasattr(session,"sid") else session.get("csrf_token")))
                    return jsonify(redact_debug(value)),200
                except StaleAnnotationRevision as error:return jsonify({"error":str(error)}),409
                except SchemaValidationError as error:return jsonify({"error":str(error),"field_errors":error.field_errors}),400
                except PermissionError as error:return jsonify({"error":str(error)}),403
                except KeyError:return jsonify({"error":"review_item_not_found"}),404
                except (ValueError,TypeError) as error:return jsonify({"error":str(error)}),400
            if path=="/api/review-metrics":
                with session_scope(db_factory) as dbs:return jsonify(db_metrics(dbs,namespace=atlas_namespace())),200
            if path=="/api/annotations":
                ident=current_identity()
                with session_scope(db_factory) as dbs:
                    rows=dbs.execute(select(Annotation).where(Annotation.reviewer_user_id==ident.get("user_id"),Annotation.namespace==atlas_namespace())).scalars().all()
                    return jsonify({"items":[annotation_to_dict(x) for x in rows],"total":len(rows)}),200
        try:status,value=api.dispatch(path,request.args.to_dict(flat=False),method=request.method,body=request.get_json(silent=True) or {})
        except (ValueError,TypeError) as error:return jsonify({"error":str(error)}),400
        if isinstance(value,dict) and "_raw" in value:return Response(value["_raw"],status,mimetype=value["_content_type"].split(";")[0],headers={"Content-Disposition":f'attachment; filename="{value["_filename"]}"'})
        return jsonify(redact_debug(value)),status
    @app.route("/app.js")
    @app.route("/style.css")
    @app.route("/design_tokens.css")
    def asset():return send_from_directory(static,request.path.lstrip("/"))
    @app.route("/",defaults={"path":""})
    @app.route("/<path:path>")
    @page_auth
    def page(path):return send_from_directory(static,"index.html")
    @app.before_request
    def workspace_rbac():
        if request.path in {"/review","/metrics","/progress"} and authenticated() and not can_use_review():return Response("Forbidden",403)
        if request.path in {"/dev","/console"} and authenticated() and not can_use_dev():return Response("Forbidden",403)
        if (request.path=="/owner" or request.path.startswith("/owner/")) and authenticated() and not can_use_owner():return Response("Forbidden",403)
        if (request.path=="/evaluation" or request.path.startswith("/evaluation/")) and authenticated() and not can_use_dev():return Response("Forbidden",403)
    return app

def serve(display_kg_root,review_root=None,host="127.0.0.1",port=8765,on_ready=None,**options):
    if options.get("public_preview") and host in ("127.0.0.1","localhost","0.0.0.0"):
        import sys
        print(f"\n{WARNING_PUBLIC_PREVIEW_HTTP}\n",file=sys.stderr)
    app=create_app(display_kg_root,review_root,**options);on_ready and on_ready();app.run(host=host,port=port,debug=False,use_reloader=False)
