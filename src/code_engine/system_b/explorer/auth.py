"""Preconfigured user storage, invite registration, and login throttling for Atlas previews."""
from __future__ import annotations
import hashlib
import json
import os
import re
import secrets
import tempfile
import time
from datetime import datetime,timezone
from pathlib import Path
from threading import Lock
from werkzeug.security import check_password_hash,generate_password_hash

USERNAME_RE=re.compile(r"^[a-z0-9_.-]{3,32}$")
WEAK_PASSWORDS={"password123","password1234","123456789","1234567890","qwerty123","qwerty12345","letmein123","admin123456","welcome123","atlaspassword"}
PUBLIC_REGISTER_ERROR="注册失败，请检查信息或联系管理员"

def hash_password(password):return generate_password_hash(password,method="pbkdf2:sha256:600000",salt_length=16)
def is_password_hash(value):return isinstance(value,str) and value.startswith("pbkdf2:sha256:") and value.count("$")==2
def utc_now_iso():return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def parse_time(value):
    if not value:return None
    if isinstance(value,(int,float)):return datetime.fromtimestamp(value,timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z","+00:00"))
def generate_invite_code():return secrets.token_urlsafe(32)
def hash_invite_code(code):return "sha256:"+hashlib.sha256(str(code).encode("utf-8")).hexdigest()
def normalize_username(username):return str(username or "").strip().casefold()
def validate_username(username):
    username=normalize_username(username)
    if not USERNAME_RE.match(username):raise ValueError("invalid_username")
    return username
def validate_display_name(value):
    value=str(value or "").strip()
    if not (1<=len(value)<=80):raise ValueError("invalid_display_name")
    return value
def validate_password_strength(password):
    password=str(password or "")
    if len(password)<12:raise ValueError("weak_password")
    if password.casefold() in WEAK_PASSWORDS:raise ValueError("weak_password")
    return password

def load_user_store(path):
    value=json.loads(Path(path).read_text(encoding="utf-8"));users=value.get("users",[]);invites=value.get("invites",[])
    if not isinstance(users,list):raise ValueError("users file must contain a users list")
    if not isinstance(invites,list):raise ValueError("users file invites field must be a list")
    for user in users:
        if not is_password_hash(user.get("password_hash")):raise ValueError(f"User {user.get('username','<unknown>')} does not contain a supported password hash")
        if "password" in user:raise ValueError("Plaintext password fields are forbidden")
    for invite in invites:
        code_hash=invite.get("code_hash")
        if not (isinstance(code_hash,str) and code_hash.startswith("sha256:")):raise ValueError(f"Invite {invite.get('label','<unknown>')} does not contain a supported code hash")
        if "code" in invite or "invite_code" in invite:raise ValueError("Plaintext invite code fields are forbidden")
    return {"users":{normalize_username(x["username"]):{**x,"username":normalize_username(x["username"])} for x in users},"invites":invites}

def load_users(path):return load_user_store(path)["users"]

def write_user_store(path,users,invites=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);payload={"users":sorted(users.values(),key=lambda x:x["username"])}
    if invites is not None:payload["invites"]=invites
    payload=json.dumps(payload,indent=2,ensure_ascii=False)+"\n"
    fd,tmp=tempfile.mkstemp(prefix=f".{path.name}.",dir=path.parent,text=True)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle:handle.write(payload);handle.flush();os.fsync(handle.fileno())
        os.chmod(tmp,0o600);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def write_users(path,users,invites=None):write_user_store(path,users,invites)

def find_usable_invite(invites,invite_code,now=None):
    now=now or datetime.now(timezone.utc);code_hash=hash_invite_code(invite_code)
    for invite in invites:
        if invite.get("code_hash")!=code_hash:continue
        if not invite.get("enabled",True):return None
        expires_at=parse_time(invite.get("expires_at"))
        if expires_at and now>expires_at:return None
        max_uses=invite.get("max_uses")
        if max_uses is not None and int(invite.get("uses",0))>=int(max_uses):return None
        return invite
    return None

class LoginLimiter:
    def __init__(self,max_attempts=5,lockout_seconds=300,clock=time.monotonic):self.max=max_attempts;self.seconds=lockout_seconds;self.clock=clock;self._failures={};self._lock=Lock()
    def _keys(self,remote,username):return (f"ip:{remote}",f"user:{username.casefold()}")
    def locked(self,remote,username):
        with self._lock:
            now=self.clock();locked=False
            for key in self._keys(remote,username):
                values=[x for x in self._failures.get(key,[]) if now-x<self.seconds];self._failures[key]=values;locked=locked or len(values)>=self.max
            return locked
    def fail(self,remote,username):
        with self._lock:
            now=self.clock()
            for key in self._keys(remote,username):self._failures.setdefault(key,[]).append(now)
    def success(self,remote,username):
        with self._lock:
            for key in self._keys(remote,username):self._failures.pop(key,None)
