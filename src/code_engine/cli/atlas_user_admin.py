"""Manage preconfigured C.O.D.E. Atlas users with hashed passwords."""
from __future__ import annotations
import argparse,getpass,os
from datetime import datetime,timedelta,timezone
from pathlib import Path
from sqlalchemy import select
from code_engine.system_b.explorer.auth import generate_invite_code,hash_invite_code,hash_password,load_user_store,utc_now_iso,write_user_store
from code_engine.system_b.persistence.database import create_atlas_engine,database_url,session_factory,session_scope
from code_engine.system_b.persistence.models import SystemSetting,User

def _store(path):return load_user_store(path) if Path(path).is_file() else {"users":{},"invites":[]}
def _users(path):return _store(path)["users"]
def _password(env_name):
    value=os.environ.get(env_name) if env_name else None
    if value is None:value=getpass.getpass("Password: ");confirm=getpass.getpass("Confirm password: ");
    else:confirm=value
    if value!=confirm:raise ValueError("Passwords do not match")
    if len(value)<12:raise ValueError("Password must be at least 12 characters")
    return value
def main(argv=None):
    p=argparse.ArgumentParser(description="Manage preconfigured C.O.D.E. Atlas users.");sub=p.add_subparsers(dest="command",required=True)
    for name in ("create-user","reset-password"):
        q=sub.add_parser(name);q.add_argument("--users-file",required=True);q.add_argument("--username",required=True);q.add_argument("--password-env")
        if name=="create-user":q.add_argument("--display-name",required=True);q.add_argument("--role",choices=("admin","developer","reviewer","pharma"),default="reviewer")
    q=sub.add_parser("list-users");q.add_argument("--users-file",required=True)
    q=sub.add_parser("disable-user");q.add_argument("--users-file",required=True);q.add_argument("--username",required=True)
    q=sub.add_parser("create-invite");q.add_argument("--users-file",required=True);q.add_argument("--label",required=True);q.add_argument("--role",choices=("admin","developer","reviewer","pharma"),default="reviewer");q.add_argument("--max-uses",type=int,default=1);q.add_argument("--expires-in-days",type=int,required=True);q.add_argument("--created-by",default="admin")
    q=sub.add_parser("list-invites");q.add_argument("--users-file",required=True)
    q=sub.add_parser("disable-invite");q.add_argument("--users-file",required=True);q.add_argument("--label",required=True)
    q=sub.add_parser("create-owner");q.add_argument("--database-url",default=None);q.add_argument("--username",required=True);q.add_argument("--display-name",required=True);q.add_argument("--password-env")
    a=p.parse_args(argv)
    if a.command=="create-owner":
        username=a.username.strip().casefold()
        if not username:raise ValueError("--username is required")
        engine=create_atlas_engine(database_url(a.database_url));factory=session_factory(engine)
        with session_scope(factory) as session:
            owners=session.execute(select(User).where(User.role=="owner",User.enabled==True)).scalars().all()  # noqa: E712
            if owners:raise ValueError("An enabled owner already exists")
            if session.execute(select(User).where(User.username==username)).scalar_one_or_none():raise ValueError(f"User already exists: {username}")
            user=User(username=username,display_name=a.display_name,password_hash=hash_password(_password(a.password_env)),role="owner",enabled=True)
            session.add(user);session.flush();session.merge(SystemSetting(key="owner_user_id",value=user.user_id))
            print(f"Created owner: {username} ({user.user_id})")
        return 0
    store=_store(a.users_file);users=store["users"];invites=store["invites"]
    if a.command=="list-users":
        for x in users.values():print(f"{x['username']}\t{x.get('display_name','')}\t{x.get('role','reviewer')}\t{'enabled' if x.get('enabled',True) else 'disabled'}")
        return 0
    if a.command=="list-invites":
        for x in invites:print(f"{x.get('label','')}\t{x.get('role','reviewer')}\t{'enabled' if x.get('enabled',True) else 'disabled'}\tuses={x.get('uses',0)}/{x.get('max_uses','')}\texpires={x.get('expires_at','')}")
        return 0
    if a.command=="create-invite":
        if a.max_uses<1:raise ValueError("--max-uses must be positive")
        if any(x.get("label")==a.label for x in invites):raise ValueError(f"Invite already exists: {a.label}")
        code=generate_invite_code();expires=(datetime.now(timezone.utc)+timedelta(days=a.expires_in_days)).replace(microsecond=0).isoformat().replace("+00:00","Z")
        invites.append({"code_hash":hash_invite_code(code),"label":a.label,"role":a.role,"enabled":True,"created_at":utc_now_iso(),"expires_at":expires,"max_uses":a.max_uses,"uses":0,"created_by":a.created_by})
        write_user_store(a.users_file,users,invites);print(f"Invite code for {a.label}: {code}");print("Store this code now; it will not be shown again.");return 0
    if a.command=="disable-invite":
        found=False
        for x in invites:
            if x.get("label")==a.label:x["enabled"]=False;found=True
        if not found:raise ValueError(f"Unknown invite: {a.label}")
        write_user_store(a.users_file,users,invites);return 0
    if a.username not in users and a.command!="create-user":raise ValueError(f"Unknown user: {a.username}")
    if a.command=="create-user":
        if a.username in users:raise ValueError(f"User already exists: {a.username}")
        users[a.username]={"username":a.username,"password_hash":hash_password(_password(a.password_env)),"display_name":a.display_name,"role":a.role,"enabled":True}
    elif a.command=="reset-password":users[a.username]["password_hash"]=hash_password(_password(a.password_env))
    elif a.command=="disable-user":users[a.username]["enabled"]=False
    write_user_store(a.users_file,users,invites);return 0
if __name__=="__main__":raise SystemExit(main())
