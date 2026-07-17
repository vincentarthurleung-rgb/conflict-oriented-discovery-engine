import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.explorer.auth import hash_password
from code_engine.system_b.explorer.explorer_server import create_app
from code_engine.system_b.persistence.database import create_atlas_engine, session_factory, session_scope
from code_engine.system_b.persistence.models import EvaluationProject, SystemSetting, User
from tests.atlas_db_test_utils import add_review_item, migrate
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests


class AtlasFrontendInitializationTests(unittest.TestCase):
    def _fixture(self, tmp):
        root = Path(tmp) / "kg"
        root.mkdir()
        KnowledgeExplorerTests().fixture(root)
        url = f"sqlite:///{tmp}/atlas.db"
        migrate(url)
        factory = session_factory(create_atlas_engine(url))
        password = hash_password("correct horse battery staple")
        with session_scope(factory) as session:
            owner = User(username="owner", display_name="Owner", password_hash=password, role="owner", enabled=True)
            reviewer = User(username="reviewer", display_name="Reviewer", password_hash=password, role="reviewer", enabled=True)
            session.add_all([owner, reviewer])
            session.flush()
            session.add(SystemSetting(key="owner_user_id", value=owner.user_id))
            add_review_item(session, "item1", case_id="case1", namespace="pilot", item_type="conflict_pair")
            session.add(EvaluationProject(name="Eleven-case Pilot Readiness", namespace="pilot", status="active", created_by_user_id=owner.user_id))
        return root, url

    def _login(self, client, username):
        page = client.get("/login").get_data(as_text=True)
        token = page.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
        return client.post("/login", data={"username": username, "password": "correct horse battery staple", "csrf_token": token})

    def test_index_references_existing_static_assets(self):
        index = Path("src/code_engine/system_b/explorer/static/index.html").read_text()
        self.assertIn('href="/style.css"', index)
        self.assertIn('src="/app.js"', index)
        self.assertTrue(Path("src/code_engine/system_b/explorer/static/app.js").is_file())
        self.assertTrue(Path("src/code_engine/system_b/explorer/static/style.css").is_file())

    def test_flask_serves_repository_static_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, url = self._fixture(tmp)
            app = create_app(root, None, require_auth=True, secret_key="x", database_url=url, require_database=True, testing=True)
            client = app.test_client()
            self.assertEqual(client.get("/app.js").get_data(), Path("src/code_engine/system_b/explorer/static/app.js").read_bytes())
            self.assertEqual(client.get("/style.css").get_data(), Path("src/code_engine/system_b/explorer/static/style.css").read_bytes())
            self.assertEqual(client.get("/static/app.js").status_code, 302)

    def test_owner_route_and_payload_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, url = self._fixture(tmp)
            app = create_app(root, None, require_auth=True, secret_key="x", database_url=url, require_database=True, testing=True)
            owner_client = app.test_client()
            self._login(owner_client, "owner")
            session_payload = owner_client.get("/api/session").get_json()
            self.assertIn("allowed_workspaces", session_payload)
            self.assertIn("owner", session_payload["allowed_workspaces"])
            self.assertEqual(owner_client.get("/owner/system").status_code, 200)
            projects = owner_client.get("/api/owner/projects").get_json()
            self.assertIn("items", projects)
            self.assertEqual(projects["items"][0]["namespace"], "pilot")
            reviewer_client = app.test_client()
            self._login(reviewer_client, "reviewer")
            self.assertEqual(reviewer_client.get("/api/owner/projects").status_code, 403)

    def test_current_app_js_initializes_owner_workspace_in_dom_harness(self):
        script = r"""
        const fs=require('fs'), vm=require('vm');
        class El{constructor(sel){this.sel=sel;this.innerHTML='';this.textContent='';this.classList={add(){},remove(){},toggle(){}};this.dataset={};this.style={};this.value='';}
          setAttribute(){} appendChild(){} remove(){} closest(){return null} addEventListener(){} querySelector(){return null}}
        const els={}; function el(sel){return els[sel]||(els[sel]=new El(sel));}
        const document={body:new El('body'),querySelector(sel){return el(sel)},querySelectorAll(){return []},createElement(tag){return new El(tag)},addEventListener(){}};
        const location={pathname:'/owner/system',search:'',href:'',reload(){}};
        const localStorage={m:{},getItem(k){return this.m[k]||null},setItem(k,v){this.m[k]=v},removeItem(k){delete this.m[k]}};
        const responses={
          '/api/session':{user:{display_name:'Owner',role:'owner'},username:'owner',role:'owner',csrf_token:'csrf',allowed_workspaces:['discover','review','library','console','owner'],debug_access:true},
          '/api/cases':{items:[]},
          '/api/owner/projects':{items:[{project_id:'p1',name:'Eleven-case Pilot Readiness',namespace:'pilot'}]},
          '/api/owner/system-state':{database_path:'data/code_atlas.db',schema_head:'0010_role_workspaces',owner:{username:'owner'},assignment_batch_count:0,adjudication_count:0,metric_result_count:0,active_invite_count:0,projects:[],review_items_by_namespace:[],review_items_by_project:[],assignment_counts:[],annotation_counts:[],gold_counts:[],metric_run_counts:[],quality_warnings:[]}
        };
        async function fetch(path){ if(!responses[path]) return {ok:false,statusText:'Not Found',json:async()=>({error:'not_found:'+path})}; return {ok:true,json:async()=>responses[path]}; }
        const ctx={console,document,location,localStorage,fetch,navigator:{},setTimeout,requestAnimationFrame:(cb)=>cb(),CSS:{escape:(s)=>String(s)},addEventListener(){}};
        ctx.window=ctx;
        vm.runInNewContext(fs.readFileSync('src/code_engine/system_b/explorer/static/app.js','utf8'),ctx,{filename:'app.js'});
        setTimeout(()=>{ console.log(JSON.stringify({nav:el('nav').innerHTML,workspace:el('#workspace').innerHTML,ownerBody:el('#owner-page-body').innerHTML})); },50);
        """
        result = subprocess.run(["node", "-e", script], check=True, text=True, capture_output=True)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertIn("Owner", payload["nav"])
        self.assertIn("System State", payload["ownerBody"])
        self.assertNotIn("Loading workspace", payload["workspace"] + payload["ownerBody"])

    def test_initialization_failure_replaces_loading(self):
        app_js = Path("src/code_engine/system_b/explorer/static/app.js").read_text()
        self.assertIn("Atlas workspace failed to load", app_js)
        self.assertIn("Stage: JavaScript initialization", app_js)


if __name__ == "__main__":
    unittest.main()
