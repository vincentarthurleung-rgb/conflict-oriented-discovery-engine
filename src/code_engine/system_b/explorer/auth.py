"""Preconfigured user storage and login throttling for Atlas previews."""
from __future__ import annotations
import json
import os
import tempfile
import time
from pathlib import Path
from threading import Lock
from werkzeug.security import check_password_hash,generate_password_hash

def hash_password(password):return generate_password_hash(password,method="pbkdf2:sha256:600000",salt_length=16)
def is_password_hash(value):return isinstance(value,str) and value.startswith("pbkdf2:sha256:") and value.count("$")==2

def load_users(path):
    value=json.loads(Path(path).read_text(encoding="utf-8"));users=value.get("users",[])
    if not isinstance(users,list):raise ValueError("users file must contain a users list")
    for user in users:
        if not is_password_hash(user.get("password_hash")):raise ValueError(f"User {user.get('username','<unknown>')} does not contain a supported password hash")
        if "password" in user:raise ValueError("Plaintext password fields are forbidden")
    return {x["username"]:x for x in users}

def write_users(path,users):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);payload=json.dumps({"users":sorted(users.values(),key=lambda x:x["username"])},indent=2,ensure_ascii=False)+"\n"
    fd,tmp=tempfile.mkstemp(prefix=f".{path.name}.",dir=path.parent,text=True)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle:handle.write(payload);handle.flush();os.fsync(handle.fileno())
        os.chmod(tmp,0o600);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

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
