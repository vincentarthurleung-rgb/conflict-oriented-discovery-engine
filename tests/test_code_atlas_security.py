import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code_engine.cli.atlas_user_admin import main as user_admin
from code_engine.system_b.explorer.auth import hash_password,is_password_hash,load_users,write_users
from code_engine.system_b.explorer.explorer_server import create_app
from tests import test_system_b_knowledge_explorer as explorer_support

class AtlasSecurityTests(unittest.TestCase):
    def setup_data(self,root,enabled=True):
        explorer_support.KnowledgeExplorerTests().fixture(root);users=root/"users.json";write_users(users,{"reviewer":{"username":"reviewer","password_hash":hash_password("correct horse battery staple"),"display_name":"Reviewer","role":"reviewer","enabled":enabled}});return users
    def login(self,client,password="correct horse battery staple"):
        page=client.get("/login").get_data(as_text=True);token=page.split('name="csrf_token" value="',1)[1].split('"',1)[0]
        return client.post("/login",data={"username":"reviewer","password":password,"csrf_token":token})
    def test_public_preview_startup_requirements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);users=self.setup_data(root)
            with self.assertRaisesRegex(ValueError,"ATLAS_SECRET_KEY"):create_app(root,public_preview=True,users_file=users)
            with self.assertRaisesRegex(FileNotFoundError,"users-file"):create_app(root,require_auth=True,secret_key="x",users_file=root/"missing")
    def test_auth_redirect_api_login_logout_and_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);users=self.setup_data(root);client=create_app(root,require_auth=True,users_file=users,secret_key="test-secret",testing=True).test_client()
            self.assertEqual(client.get("/").status_code,302);api=client.get("/api/summary");self.assertEqual(api.status_code,401);self.assertEqual(api.get_json()["error"],"authentication_required")
            bad=self.login(client,"wrong password");self.assertIn("Invalid credentials or temporarily locked",bad.get_data(as_text=True));good=self.login(client);self.assertEqual(good.status_code,302)
            response=client.get("/api/summary");self.assertEqual(response.status_code,200)
            for key in ("X-Content-Type-Options","X-Frame-Options","Referrer-Policy","Content-Security-Policy","Cache-Control"):self.assertIn(key,response.headers)
            client.get("/logout");self.assertEqual(client.get("/api/summary").status_code,401)
    def test_disabled_user_and_lockout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);users=self.setup_data(root,enabled=False);client=create_app(root,require_auth=True,users_file=users,secret_key="x",max_failed_attempts=2,lockout_seconds=300,testing=True).test_client()
            self.assertIn("Invalid credentials",self.login(client).get_data(as_text=True));self.assertIn("Invalid credentials",self.login(client).get_data(as_text=True));self.assertTrue(client.application.extensions["atlas_limiter"].locked("127.0.0.1","different-user"));self.assertIn("temporarily locked",self.login(client).get_data(as_text=True))
    def test_csrf_write_protection_and_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);users=self.setup_data(root);queue=[{"review_item_id":"item","case_id":"case","item_type":"fulltext_l1_claim"}];explorer_support.write_jsonl(root/"manual_review_queue.jsonl",queue)
            client=create_app(root,root,require_auth=True,users_file=users,secret_key="x",testing=True).test_client();self.login(client)
            self.assertEqual(client.post("/api/annotation/item",json={"final_label":"VALID"}).status_code,403);token=client.get("/api/session").get_json()["csrf_token"]
            saved=client.post("/api/annotation/item",json={"final_label":"VALID"},headers={"X-CSRF-Token":token});self.assertEqual(saved.status_code,200);self.assertEqual(saved.get_json()["final_label"],"VALID")
    def test_hash_storage_and_user_admin(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"users.json"
            with patch.dict(os.environ,{"ATLAS_TEST_PASSWORD":"a sufficiently long password"}):self.assertEqual(user_admin(["create-user","--users-file",str(path),"--username","vincent","--display-name","Vincent","--role","admin","--password-env","ATLAS_TEST_PASSWORD"]),0)
            raw=path.read_text();self.assertNotIn("a sufficiently long password",raw);user=load_users(path)["vincent"];self.assertTrue(is_password_hash(user["password_hash"]));self.assertNotIn("password",user)

if __name__=="__main__":unittest.main()
