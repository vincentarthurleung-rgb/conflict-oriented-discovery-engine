"""Flask application for authenticated C.O.D.E. Atlas previews."""
from __future__ import annotations
import logging
import secrets
from functools import wraps
from pathlib import Path
from urllib.parse import parse_qs
from flask import Flask,Response,jsonify,redirect,request,send_from_directory,session,url_for
from werkzeug.security import check_password_hash
from .auth import LoginLimiter,load_users
from .explorer_api import ExplorerAPI

LOG=logging.getLogger("code_engine.atlas.security")
LOGIN_HTML="""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>C.O.D.E. Atlas Login</title><link rel="stylesheet" href="/style.css"></head><body class="login-page"><main class="login-card"><h1>C.O.D.E. Atlas</h1><h2>Biomedical Evidence &amp; Mechanism Explorer</h2><p>Public preview access is restricted.</p>{error}<form method="post"><input type="hidden" name="csrf_token" value="{csrf}"><label>Username<input name="username" autocomplete="username" required></label><label>Password<input type="password" name="password" autocomplete="current-password" required></label><button class="button" type="submit">Sign in</button></form></main></body></html>"""

def create_app(display_kg_root,review_root=None,*,require_auth=False,users_file=None,secret_key=None,public_preview=False,max_failed_attempts=5,lockout_seconds=300,testing=False):
    if public_preview:require_auth=True
    if public_preview and not secret_key:raise ValueError("ATLAS_SECRET_KEY is required in --public-preview mode")
    if require_auth and (not users_file or not Path(users_file).is_file()):raise FileNotFoundError("Authentication requires an existing --users-file")
    users=load_users(users_file) if require_auth else {};api=ExplorerAPI(display_kg_root,review_root);static=Path(__file__).parent/"static"
    app=Flask(__name__,static_folder=None);app.secret_key=secret_key or secrets.token_urlsafe(48);app.config.update(TESTING=testing,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax",SESSION_COOKIE_SECURE=bool(public_preview))
    limiter=LoginLimiter(max_failed_attempts,lockout_seconds);app.extensions["atlas_api"]=api;app.extensions["atlas_limiter"]=limiter
    def authenticated():return not require_auth or bool(session.get("atlas_user"))
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
        response.headers["X-Content-Type-Options"]="nosniff";response.headers["X-Frame-Options"]="DENY";response.headers["Referrer-Policy"]="no-referrer";response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
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
            if limiter.locked(remote,username):LOG.warning("atlas_auth_locked remote_addr=%s",remote);error="Invalid credentials or temporarily locked."
            else:
                user=users.get(username);valid=bool(user and user.get("enabled",True) and check_password_hash(user["password_hash"],request.form.get("password","")))
                if valid:
                    limiter.success(remote,username);session.clear();session["atlas_user"]={"username":username,"display_name":user.get("display_name",username),"role":user.get("role","reviewer")};session["csrf_token"]=secrets.token_urlsafe(32);LOG.info("atlas_auth_success username=%s",username);destination=request.args.get("next") or "/";destination=destination if destination.startswith("/") and not destination.startswith("//") else "/";return redirect(destination)
                limiter.fail(remote,username);LOG.warning("atlas_auth_failed username=%s remote_addr=%s",username or "<empty>",remote);error="Invalid credentials or temporarily locked."
        return LOGIN_HTML.format(error=f'<p class="error">{error}</p>' if error else "",csrf=token)
    @app.route("/logout")
    def logout():session.clear();return redirect("/login" if require_auth else "/")
    @app.route("/api/session")
    def api_session():
        if not authenticated():return jsonify({"error":"authentication_required"}),401
        return jsonify({"user":session.get("atlas_user"),"csrf_token":csrf(),"auth_required":require_auth})
    @app.route("/api/<path:subpath>",methods=["GET","POST"])
    def api_route(subpath):
        if not authenticated():return jsonify({"error":"authentication_required"}),401
        path="/api/"+subpath
        if request.method=="POST" and path in {"/api/review-metrics/recompute"} or (request.method=="POST" and path.startswith("/api/annotation/")):
            if not secrets.compare_digest(request.headers.get("X-CSRF-Token",""),csrf()):return jsonify({"error":"csrf_token_invalid"}),403
        try:status,value=api.dispatch(path,request.args.to_dict(flat=False),method=request.method,body=request.get_json(silent=True) or {})
        except (ValueError,TypeError) as error:return jsonify({"error":str(error)}),400
        if isinstance(value,dict) and "_raw" in value:return Response(value["_raw"],status,mimetype=value["_content_type"].split(";")[0],headers={"Content-Disposition":f'attachment; filename="{value["_filename"]}"'})
        return jsonify(value),status
    @app.route("/app.js")
    @app.route("/style.css")
    def asset():return send_from_directory(static,request.path.lstrip("/"))
    @app.route("/",defaults={"path":""})
    @app.route("/<path:path>")
    @page_auth
    def page(path):return send_from_directory(static,"index.html")
    return app

def serve(display_kg_root,review_root=None,host="127.0.0.1",port=8765,on_ready=None,**options):
    app=create_app(display_kg_root,review_root,**options);on_ready and on_ready();app.run(host=host,port=port,debug=False,use_reloader=False)
