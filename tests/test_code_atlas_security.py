import json
import os
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

from code_engine.cli.atlas_user_admin import main as user_admin
from code_engine.system_b.explorer.auth import hash_invite_code,hash_password,is_password_hash,load_user_store,load_users,utc_now_iso,write_user_store,write_users
from code_engine.system_b.explorer.explorer_server import create_app
from tests import test_system_b_knowledge_explorer as explorer_support

class AtlasSecurityTests(unittest.TestCase):
    def setup_data(self,root,enabled=True):
        explorer_support.KnowledgeExplorerTests().fixture(root);users=root/"users.json";write_users(users,{"reviewer":{"username":"reviewer","password_hash":hash_password("correct horse battery staple"),"display_name":"Reviewer","role":"reviewer","enabled":enabled}});return users
    def setup_role_data(self,root):
        explorer_support.KnowledgeExplorerTests().fixture(root);users=root/"users.json";write_user_store(users,{
            "reviewer":{"username":"reviewer","password_hash":hash_password("correct horse battery staple"),"display_name":"Reviewer","role":"reviewer","enabled":True},
            "admin":{"username":"admin","password_hash":hash_password("correct horse battery staple"),"display_name":"Admin","role":"admin","enabled":True},
            "developer":{"username":"developer","password_hash":hash_password("correct horse battery staple"),"display_name":"Developer","role":"developer","enabled":True},
        },[]);explorer_support.write_jsonl(root/"manual_review_queue.jsonl",[{"review_item_id":"item","case_id":"case","item_type":"fulltext_l1_claim","source_file":"l35.jsonl","source_line":12,"bundle_path":"/tmp/bundle","evidence_sentence":"Evidence text"}]);return users
    def login(self,client,password="correct horse battery staple"):
        page=client.get("/login").get_data(as_text=True);token=page.split('name="csrf_token" value="',1)[1].split('"',1)[0]
        return client.post("/login",data={"username":"reviewer","password":password,"csrf_token":token})
    def login_as(self,client,username,password):
        page=client.get("/login").get_data(as_text=True);token=page.split('name="csrf_token" value="',1)[1].split('"',1)[0]
        return client.post("/login",data={"username":username,"password":password,"csrf_token":token})
    def register_token(self,client):
        page=client.get("/register").get_data(as_text=True)
        return page.split('name="csrf_token" value="',1)[1].split('"',1)[0]
    def invite(self,code="invite-code-with-enough-entropy-123",label="batch",max_uses=10,days=14,enabled=True):
        expires=(datetime.now(timezone.utc)+timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00","Z")
        return {"code_hash":hash_invite_code(code),"label":label,"role":"reviewer","enabled":enabled,"created_at":utc_now_iso(),"expires_at":expires,"max_uses":max_uses,"uses":0,"created_by":"admin"}
    def test_public_preview_startup_requirements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);users=self.setup_data(root)
            with self.assertRaisesRegex(ValueError,"ATLAS_SECRET_KEY"):create_app(root,public_preview=True,users_file=users)
            with self.assertRaisesRegex(FileNotFoundError,"users-file"):create_app(root,require_auth=True,secret_key="x",users_file=root/"missing")
    def test_auth_redirect_api_login_logout_and_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);users=self.setup_data(root);client=create_app(root,require_auth=True,users_file=users,secret_key="test-secret",testing=True).test_client()
            self.assertEqual(client.get("/").status_code,302);api=client.get("/api/summary");self.assertEqual(api.status_code,401);self.assertEqual(api.get_json()["error"],"authentication_required")
            bad=self.login(client,"wrong password");self.assertIn("用户名或密码错误，或账号不可用。",bad.get_data(as_text=True));good=self.login(client);self.assertEqual(good.status_code,302)
            response=client.get("/api/summary");self.assertEqual(response.status_code,200)
            for key in ("X-Content-Type-Options","X-Frame-Options","Referrer-Policy","Content-Security-Policy","Permissions-Policy","Cache-Control"):self.assertIn(key,response.headers)
            self.assertIn("object-src 'none'",response.headers["Content-Security-Policy"]);self.assertIn("clipboard-write=(self)",response.headers["Permissions-Policy"])
            token=client.get("/api/session").get_json()["csrf_token"];self.assertEqual(client.get("/logout").status_code,302);self.assertEqual(client.get("/api/summary").status_code,200)
            self.assertEqual(client.post("/api/logout",headers={"X-CSRF-Token":token}).status_code,200);self.assertEqual(client.get("/api/summary").status_code,401)
    def test_login_errors_do_not_enumerate_users(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);users=self.setup_data(root);client=create_app(root,require_auth=True,users_file=users,secret_key="x",testing=True).test_client()
            existing=self.login_as(client,"reviewer","wrong password").get_data(as_text=True)
            missing=self.login_as(client,"missing","wrong password").get_data(as_text=True)
            self.assertIn("用户名或密码错误，或账号不可用。",existing);self.assertIn("用户名或密码错误，或账号不可用。",missing)
            self.assertNotIn("missing",missing)
    def test_disabled_user_and_lockout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);users=self.setup_data(root,enabled=False);client=create_app(root,require_auth=True,users_file=users,secret_key="x",max_failed_attempts=2,lockout_seconds=300,testing=True).test_client()
            self.assertIn("用户名或密码错误",self.login(client).get_data(as_text=True));self.assertIn("用户名或密码错误",self.login(client).get_data(as_text=True));self.assertTrue(client.application.extensions["atlas_limiter"].locked("127.0.0.1","different-user"));self.assertIn("用户名或密码错误",self.login(client).get_data(as_text=True))
    def test_csrf_write_protection_and_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);users=self.setup_data(root);queue=[{"review_item_id":"item","case_id":"case","item_type":"fulltext_l1_claim"}];explorer_support.write_jsonl(root/"manual_review_queue.jsonl",queue)
            client=create_app(root,root,require_auth=True,users_file=users,secret_key="x",testing=True).test_client();self.login(client)
            self.assertEqual(client.post("/api/annotation/item",json={"final_label":"VALID"}).status_code,403);token=client.get("/api/session").get_json()["csrf_token"]
            saved=client.post("/api/annotation/item",json={"final_label":"VALID"},headers={"X-CSRF-Token":token});self.assertEqual(saved.status_code,200);self.assertEqual(saved.get_json()["final_label"],"VALID")
            self.assertEqual(client.post("/api/logout").status_code,403)
            self.assertEqual(client.post("/api/logout",headers={"X-CSRF-Token":token}).status_code,200)
    def test_session_cookie_flags_public_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);users=self.setup_data(root);client=create_app(root,require_auth=True,public_preview=True,users_file=users,secret_key="x",testing=True).test_client()
            response=client.get("/login");cookie=response.headers.get("Set-Cookie","")
            self.assertIn("HttpOnly",cookie);self.assertIn("SameSite=Lax",cookie);self.assertIn("Secure",cookie)
    def test_hash_storage_and_user_admin(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"users.json"
            with patch.dict(os.environ,{"ATLAS_TEST_PASSWORD":"a sufficiently long password"}):self.assertEqual(user_admin(["create-user","--users-file",str(path),"--username","vincent","--display-name","Vincent","--role","admin","--password-env","ATLAS_TEST_PASSWORD"]),0)
            raw=path.read_text();self.assertNotIn("a sufficiently long password",raw);user=load_users(path)["vincent"];self.assertTrue(is_password_hash(user["password_hash"]));self.assertNotIn("password",user)
            self.assertEqual(user_admin(["create-invite","--users-file",str(path),"--label","pharmacy_batch","--role","reviewer","--max-uses","2","--expires-in-days","14"]),0)
            store=load_user_store(path);self.assertEqual(len(store["invites"]),1);self.assertNotIn("invite_code",path.read_text());self.assertNotIn("Invite code for pharmacy_batch",path.read_text())
            self.assertEqual(user_admin(["disable-invite","--users-file",str(path),"--label","pharmacy_batch"]),0);self.assertFalse(load_user_store(path)["invites"][0]["enabled"])
    def test_plaintext_password_and_invite_config_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"users.json";path.write_text(json.dumps({"users":[{"username":"bad","password":"plaintext","password_hash":hash_password("long enough password"),"display_name":"Bad"}]}))
            with self.assertRaisesRegex(ValueError,"Plaintext password"):load_users(path)
            path.write_text(json.dumps({"users":[],"invites":[{"label":"bad","code":"plaintext","code_hash":hash_invite_code("x")}]}))
            with self.assertRaisesRegex(ValueError,"Plaintext invite"):load_user_store(path)
    def test_registration_disabled_invalid_valid_duplicate_max_uses_and_expired(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);explorer_support.KnowledgeExplorerTests().fixture(root);path=root/"users.json";code="invite-code-with-enough-entropy-123";write_user_store(path,{},[self.invite(code=code,max_uses=1)])
            disabled=create_app(root,require_auth=True,users_file=path,secret_key="x",testing=True).test_client()
            self.assertEqual(disabled.get("/api/registration-config").get_json()["allow_registration"],False)
            self.assertEqual(disabled.post("/api/register",json={}).status_code,403)
            client=create_app(root,require_auth=True,users_file=path,secret_key="x",allow_registration=True,testing=True).test_client();token=self.register_token(client)
            bad=client.post("/api/register",json={"username":"student","display_name":"Student","password":"a sufficiently long password","confirm_password":"a sufficiently long password","invite_code":"wrong"},headers={"X-CSRF-Token":token})
            self.assertEqual(bad.status_code,400);self.assertEqual(bad.get_json()["error"],"注册失败，请检查信息或联系管理员")
            good=client.post("/api/register",json={"username":"Student.One","display_name":"Student <One>","password":"a sufficiently long password","confirm_password":"a sufficiently long password","invite_code":code},headers={"X-CSRF-Token":token})
            self.assertEqual(good.status_code,201);store=load_user_store(path);self.assertIn("student.one",store["users"]);self.assertEqual(store["users"]["student.one"]["role"],"reviewer");self.assertEqual(store["invites"][0]["uses"],1);self.assertNotIn(code,path.read_text())
            duplicate=client.post("/api/register",json={"username":"student.one","display_name":"Student","password":"a sufficiently long password","confirm_password":"a sufficiently long password","invite_code":code},headers={"X-CSRF-Token":token})
            self.assertEqual(duplicate.status_code,400);self.assertEqual(duplicate.get_json()["error"],"注册失败，请检查信息或联系管理员")
            exhausted=client.post("/api/register",json={"username":"student2","display_name":"Student 2","password":"a sufficiently long password","confirm_password":"a sufficiently long password","invite_code":code},headers={"X-CSRF-Token":token})
            self.assertEqual(exhausted.status_code,400)
            expired=root/"expired.json";expired_code="expired-invite-code-with-enough-entropy";write_user_store(expired,{},[self.invite(code=expired_code,days=-1)])
            expired_client=create_app(root,require_auth=True,users_file=expired,secret_key="x",allow_registration=True,testing=True).test_client();expired_token=self.register_token(expired_client)
            response=expired_client.post("/api/register",json={"username":"student3","display_name":"Student 3","password":"a sufficiently long password","confirm_password":"a sufficiently long password","invite_code":expired_code},headers={"X-CSRF-Token":expired_token})
            self.assertEqual(response.status_code,400)
    def test_register_rate_limit_and_csrf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);explorer_support.KnowledgeExplorerTests().fixture(root);path=root/"users.json";write_user_store(path,{},[self.invite()])
            client=create_app(root,require_auth=True,users_file=path,secret_key="x",allow_registration=True,max_failed_attempts=2,lockout_seconds=300,testing=True).test_client();token=self.register_token(client)
            payload={"username":"student","display_name":"Student","password":"a sufficiently long password","confirm_password":"a sufficiently long password","invite_code":"bad"}
            self.assertEqual(client.post("/api/register",json=payload).status_code,403)
            self.assertEqual(client.post("/api/register",json=payload,headers={"X-CSRF-Token":token}).status_code,400)
            self.assertEqual(client.post("/api/register",json=payload,headers={"X-CSRF-Token":token}).status_code,400)
            self.assertEqual(client.post("/api/register",json=payload,headers={"X-CSRF-Token":token}).status_code,429)
    def test_role_allowed_modes_and_debug_redaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);users=self.setup_role_data(root)
            reviewer=create_app(root,root,require_auth=True,users_file=users,secret_key="x",testing=True).test_client();self.login_as(reviewer,"reviewer","correct horse battery staple")
            session_payload=reviewer.get("/api/session").get_json();self.assertEqual(session_payload["role"],"reviewer");self.assertEqual(session_payload["allowed_modes"],["pharma","reviewer"]);self.assertTrue(session_payload["registration_enabled"] is False)
            item=reviewer.get("/api/review-items?limit=1").get_json()["items"][0];self.assertNotIn("source_file",item);self.assertNotIn("source_line",item);self.assertNotIn("bundle_path",item)
            triple=reviewer.get("/api/triples?limit=1").get_json()["items"][0];self.assertNotIn("display_priority_score_v2",triple)
            admin=create_app(root,root,require_auth=True,users_file=users,secret_key="x",testing=True).test_client();self.login_as(admin,"admin","correct horse battery staple")
            admin_session=admin.get("/api/session").get_json();self.assertEqual(admin_session["allowed_modes"],["pharma","reviewer","developer"])
            admin_item=admin.get("/api/review-items?limit=1").get_json()["items"][0];self.assertIn("source_file",admin_item);self.assertIn("source_line",admin_item);self.assertIn("bundle_path",admin_item)
            developer=create_app(root,root,require_auth=True,users_file=users,secret_key="x",testing=True).test_client();self.login_as(developer,"developer","correct horse battery staple")
            self.assertIn("developer",developer.get("/api/session").get_json()["allowed_modes"])

if __name__=="__main__":unittest.main()
