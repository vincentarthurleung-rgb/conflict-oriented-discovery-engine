"""Flask application for authenticated C.O.D.E. Atlas previews."""
from __future__ import annotations
import logging
import secrets
from functools import wraps
from pathlib import Path
from urllib.parse import parse_qs
from flask import Flask,Response,jsonify,redirect,request,send_from_directory,session,url_for
from werkzeug.security import check_password_hash
from .auth import PUBLIC_REGISTER_ERROR,LoginLimiter,find_usable_invite,hash_password,load_user_store,utc_now_iso,validate_display_name,validate_password_strength,validate_username,write_user_store
from .explorer_api import ExplorerAPI

LOG=logging.getLogger("code_engine.atlas.security")
WARNING_PUBLIC_PREVIEW_HTTP = (
    "WARNING: --public-preview is enabled but the server is likely running on HTTP. "
    "Secure session cookies require HTTPS. Login and session functionality will not work over HTTP. "
    "Use --no-auth for local testing over HTTP, or configure HTTPS for public-preview."
)
LOGIN_ERROR="用户名或密码错误，或账号不可用。"
ROLE_ALLOWED_MODES={"admin":["pharma","reviewer","developer"],"developer":["pharma","reviewer","developer"],"reviewer":["pharma","reviewer"],"pharma":["pharma"]}
DEBUG_FIELDS={"source_file","source_line","bundle_path","display_priority_score","display_priority_score_v2","noise_risk_score","chain_noise_risk_score","validator_annotations","validator_details","raw_json","raw","bridge_provenance","fulltext_provenance"}
LOGIN_HTML="""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>C.O.D.E. Atlas Login</title><link rel="stylesheet" href="/style.css"></head><body class="login-page"><main class="login-card"><h1>C.O.D.E. Atlas</h1><h2>Biomedical Evidence &amp; Mechanism Explorer</h2><p>Public preview access is restricted.</p>{error}<form method="post"><input type="hidden" name="csrf_token" value="{csrf}"><label>Username<input name="username" autocomplete="username" required></label><label>Password<input type="password" name="password" autocomplete="current-password" required></label><button class="button" type="submit">Sign in</button></form><p id="registration-link" class="muted" hidden>没有账号？<a href="/register">使用邀请码注册</a></p><script>fetch('/api/registration-config').then(function(r){{return r.json()}}).then(function(x){{if(x.allow_registration)document.getElementById('registration-link').hidden=false}}).catch(function(){{}})</script>{warning}</main></body></html>"""
REGISTER_HTML="""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>C.O.D.E. Atlas Register</title><link rel="stylesheet" href="/style.css"></head><body class="login-page"><main class="login-card"><h1>邀请码注册</h1><h2>C.O.D.E. Atlas</h2><p>注册仅面向收到邀请码的审核人员。注册成功后请返回登录页登录。</p><div id="register-message"></div><form id="register-form"><input type="hidden" name="csrf_token" value="{csrf}"><label>用户名<input name="username" autocomplete="username" minlength="3" maxlength="32" pattern="[A-Za-z0-9_.-]{{3,32}}" required></label><label>显示名<input name="display_name" autocomplete="name" minlength="1" maxlength="80" required></label><label>密码<input type="password" name="password" autocomplete="new-password" minlength="12" required></label><label>确认密码<input type="password" name="confirm_password" autocomplete="new-password" minlength="12" required></label><label>邀请码<input name="invite_code" autocomplete="off" required></label><button class="button" type="submit">注册</button><a class="button-sm" href="/login">返回登录</a></form><script>fetch('/api/registration-config').then(function(r){{return r.json()}}).then(function(x){{if(!x.allow_registration)location.href='/login'}});document.getElementById('register-form').addEventListener('submit',async function(e){{e.preventDefault();var f=e.target,b=f.querySelector('button'),m=document.getElementById('register-message');if(f.password.value!==f.confirm_password.value){{m.innerHTML='<p class="error">注册失败，请检查信息或联系管理员</p>';return}}b.disabled=true;m.textContent='';try{{var r=await fetch('/api/register',{{method:'POST',headers:{{'Content-Type':'application/json','X-CSRF-Token':f.csrf_token.value}},body:JSON.stringify({{username:f.username.value,display_name:f.display_name.value,password:f.password.value,confirm_password:f.confirm_password.value,invite_code:f.invite_code.value}})}});var data=await r.json();if(r.ok){{m.innerHTML='<p class="badge saved-indicator">注册成功，请登录</p>';f.reset()}}else{{m.innerHTML='<p class="error">'+(data.error||'注册失败，请检查信息或联系管理员')+'</p>'}}}}catch(err){{m.innerHTML='<p class="error">注册失败，请检查信息或联系管理员</p>'}}finally{{b.disabled=false}}}})</script></main></body></html>"""

def create_app(display_kg_root,review_root=None,*,require_auth=False,users_file=None,secret_key=None,public_preview=False,allow_registration=False,max_failed_attempts=5,lockout_seconds=300,testing=False):
    if public_preview:require_auth=True
    if public_preview and not secret_key:raise ValueError("ATLAS_SECRET_KEY is required in --public-preview mode")
    if require_auth and (not users_file or not Path(users_file).is_file()):raise FileNotFoundError("Authentication requires an existing --users-file")
    store=load_user_store(users_file) if require_auth else {"users":{},"invites":[]};users=store["users"];invites=store["invites"];users_file_path=Path(users_file) if users_file else None;api=ExplorerAPI(display_kg_root,review_root);static=Path(__file__).parent/"static"
    app=Flask(__name__,static_folder=None);app.secret_key=secret_key or secrets.token_urlsafe(48);app.config.update(TESTING=testing,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax",SESSION_COOKIE_SECURE=bool(public_preview))
    limiter=LoginLimiter(max_failed_attempts,lockout_seconds);register_limiter=LoginLimiter(max_failed_attempts,lockout_seconds);app.extensions["atlas_api"]=api;app.extensions["atlas_limiter"]=limiter;app.extensions["atlas_register_limiter"]=register_limiter
    def authenticated():return not require_auth or bool(session.get("atlas_user"))
    def current_role():
        if not require_auth:return "developer"
        user=session.get("atlas_user") or {}
        return user.get("role","reviewer")
    def allowed_modes_for_role(role):return ROLE_ALLOWED_MODES.get(role,ROLE_ALLOWED_MODES["reviewer"])
    def can_view_debug():return current_role() in {"admin","developer"}
    def can_use_review():return not require_auth or current_role() in {"admin","developer","reviewer"}
    def can_use_dev():return not require_auth or current_role() in {"admin","developer"}
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
                user=users.get(normalized);valid=bool(user and user.get("enabled",True) and check_password_hash(user["password_hash"],request.form.get("password","")))
                if valid:
                    limiter.success(remote,normalized);session.clear();session["atlas_user"]={"username":normalized,"display_name":user.get("display_name",normalized),"role":user.get("role","reviewer")};session["csrf_token"]=secrets.token_urlsafe(32);user["last_login_at"]=utc_now_iso();user["failed_login_count"]=0;users_file_path and write_user_store(users_file_path,users,invites);LOG.info("atlas_auth_success username=%s",normalized);destination=request.args.get("next") or "/";destination=destination if destination.startswith("/") and not destination.startswith("//") else "/";return redirect(destination)
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
            if username in users:raise ValueError("duplicate_username")
            invite=find_usable_invite(invites,data.get("invite_code",""))
            if not invite:raise ValueError("invalid_invite")
            role=invite.get("role","reviewer") if invite.get("role") in {"admin","developer","reviewer","pharma"} else "reviewer"
            users[username]={"username":username,"password_hash":hash_password(password),"display_name":display_name,"role":role,"enabled":True,"created_at":utc_now_iso(),"failed_login_count":0}
            invite["uses"]=int(invite.get("uses",0))+1;write_user_store(users_file_path,users,invites);register_limiter.success(remote,username);LOG.info("atlas_register_success username=%s role=%s invite_label=%s",username,role,invite.get("label",""));return jsonify({"ok":True,"message":"注册成功，请登录"}),201
        except Exception as error:
            register_limiter.fail(remote,username);LOG.warning("atlas_register_failed remote_addr=%s reason=%s",remote,type(error).__name__);return jsonify({"error":PUBLIC_REGISTER_ERROR}),400
    @app.route("/api/session")
    def api_session():
        if not authenticated():return jsonify({"error":"authentication_required"}),401
        user=session.get("atlas_user") or None;role=current_role();payload={"user":user,"csrf_token":csrf(),"auth_required":require_auth,"allowed_modes":allowed_modes_for_role(role),"registration_enabled":bool(require_auth and allow_registration)}
        if user:payload.update({"username":user.get("username"),"display_name":user.get("display_name"),"role":role})
        else:payload.update({"username":None,"display_name":None,"role":role})
        return jsonify(payload)
    @app.route("/api/<path:subpath>",methods=["GET","POST"])
    def api_route(subpath):
        if not authenticated():return jsonify({"error":"authentication_required"}),401
        path="/api/"+subpath
        if path.startswith(("/api/review","/api/annotation","/api/annotations")) and not can_use_review():return jsonify({"error":"forbidden"}),403
        if request.method in {"POST","PUT","DELETE"}:
            if not secrets.compare_digest(request.headers.get("X-CSRF-Token",""),csrf()):return jsonify({"error":"csrf_token_invalid"}),403
        try:status,value=api.dispatch(path,request.args.to_dict(flat=False),method=request.method,body=request.get_json(silent=True) or {})
        except (ValueError,TypeError) as error:return jsonify({"error":str(error)}),400
        if isinstance(value,dict) and "_raw" in value:return Response(value["_raw"],status,mimetype=value["_content_type"].split(";")[0],headers={"Content-Disposition":f'attachment; filename="{value["_filename"]}"'})
        return jsonify(redact_debug(value)),status
    @app.route("/app.js")
    @app.route("/style.css")
    def asset():return send_from_directory(static,request.path.lstrip("/"))
    @app.route("/",defaults={"path":""})
    @app.route("/<path:path>")
    @page_auth
    def page(path):return send_from_directory(static,"index.html")
    @app.before_request
    def workspace_rbac():
        if request.path in {"/review","/metrics","/progress"} and authenticated() and not can_use_review():return Response("Forbidden",403)
        if request.path=="/dev" and authenticated() and not can_use_dev():return Response("Forbidden",403)
    return app

def serve(display_kg_root,review_root=None,host="127.0.0.1",port=8765,on_ready=None,**options):
    if options.get("public_preview") and host in ("127.0.0.1","localhost","0.0.0.0"):
        import sys
        print(f"\n{WARNING_PUBLIC_PREVIEW_HTTP}\n",file=sys.stderr)
    app=create_app(display_kg_root,review_root,**options);on_ready and on_ready();app.run(host=host,port=port,debug=False,use_reloader=False)
