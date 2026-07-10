import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.explorer.auth import hash_password,write_user_store
from code_engine.system_b.explorer.explorer_server import create_app
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests


PASSWORD="correct horse battery staple"


class AtlasWorkspaceRoleTests(unittest.TestCase):
    def setup_users(self,root):
        KnowledgeExplorerTests().fixture(root)
        users=root/"users.json"
        write_user_store(users,{
            "pharma":{"username":"pharma","password_hash":hash_password(PASSWORD),"display_name":"Pharma Student","role":"pharma","enabled":True},
            "reviewer":{"username":"reviewer","password_hash":hash_password(PASSWORD),"display_name":"Reviewer","role":"reviewer","enabled":True},
            "developer":{"username":"developer","password_hash":hash_password(PASSWORD),"display_name":"Developer","role":"developer","enabled":True},
        },[])
        return users

    def login_as(self,client,username):
        page=client.get("/login").get_data(as_text=True)
        token=page.split('name="csrf_token" value="',1)[1].split('"',1)[0]
        return client.post("/login",data={"username":username,"password":PASSWORD,"csrf_token":token})

    def test_workspace_pages_are_role_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);users=self.setup_users(root)

            pharma=create_app(root,root,require_auth=True,users_file=users,secret_key="x",testing=True).test_client()
            self.assertEqual(self.login_as(pharma,"pharma").status_code,302)
            self.assertEqual(pharma.get("/api/session").get_json()["allowed_modes"],["pharma"])
            for path in ("/","/cases","/evidence","/graph","/help"):
                self.assertEqual(pharma.get(path).status_code,200,path)
            for path in ("/review","/progress","/dev"):
                self.assertEqual(pharma.get(path).status_code,403,path)
            self.assertEqual(pharma.get("/api/review-items").status_code,403)

            reviewer=create_app(root,root,require_auth=True,users_file=users,secret_key="x",testing=True).test_client()
            self.assertEqual(self.login_as(reviewer,"reviewer").status_code,302)
            self.assertEqual(reviewer.get("/api/session").get_json()["allowed_modes"],["pharma","reviewer"])
            self.assertEqual(reviewer.get("/review").status_code,200)
            self.assertEqual(reviewer.get("/progress").status_code,200)
            self.assertEqual(reviewer.get("/dev").status_code,403)

            developer=create_app(root,root,require_auth=True,users_file=users,secret_key="x",testing=True).test_client()
            self.assertEqual(self.login_as(developer,"developer").status_code,302)
            self.assertEqual(developer.get("/dev").status_code,200)


if __name__=="__main__":
    unittest.main()
