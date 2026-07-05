"""Manage preconfigured C.O.D.E. Atlas users with hashed passwords."""
from __future__ import annotations
import argparse,getpass,os
from pathlib import Path
from code_engine.system_b.explorer.auth import hash_password,load_users,write_users

def _users(path):return load_users(path) if Path(path).is_file() else {}
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
        if name=="create-user":q.add_argument("--display-name",required=True);q.add_argument("--role",choices=("admin","reviewer"),default="reviewer")
    q=sub.add_parser("list-users");q.add_argument("--users-file",required=True)
    q=sub.add_parser("disable-user");q.add_argument("--users-file",required=True);q.add_argument("--username",required=True)
    a=p.parse_args(argv);users=_users(a.users_file)
    if a.command=="list-users":
        for x in users.values():print(f"{x['username']}\t{x.get('display_name','')}\t{x.get('role','reviewer')}\t{'enabled' if x.get('enabled',True) else 'disabled'}")
        return 0
    if a.username not in users and a.command!="create-user":raise ValueError(f"Unknown user: {a.username}")
    if a.command=="create-user":
        if a.username in users:raise ValueError(f"User already exists: {a.username}")
        users[a.username]={"username":a.username,"password_hash":hash_password(_password(a.password_env)),"display_name":a.display_name,"role":a.role,"enabled":True}
    elif a.command=="reset-password":users[a.username]["password_hash"]=hash_password(_password(a.password_env))
    elif a.command=="disable-user":users[a.username]["enabled"]=False
    write_users(a.users_file,users);return 0
if __name__=="__main__":raise SystemExit(main())
