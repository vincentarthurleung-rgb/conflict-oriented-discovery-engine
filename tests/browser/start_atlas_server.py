from __future__ import annotations

import os
import tempfile
from pathlib import Path

from code_engine.system_b.explorer.auth import hash_password
from code_engine.system_b.explorer.explorer_server import create_app
from code_engine.system_b.persistence.database import create_atlas_engine, session_factory, session_scope
from code_engine.system_b.persistence.models import Assignment, EvaluationProject, SystemSetting, User
from tests.atlas_db_test_utils import add_review_item, migrate
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests


def main() -> None:
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name) / "kg"
    root.mkdir(parents=True, exist_ok=True)
    KnowledgeExplorerTests().fixture(root)
    url = f"sqlite:///{tmp.name}/atlas.db"
    migrate(url)
    factory = session_factory(create_atlas_engine(url))
    password = hash_password("correct horse battery staple")
    with session_scope(factory) as session:
        owner = User(username="owner", display_name="Owner", password_hash=password, role="owner", enabled=True)
        primary = User(username="primary", display_name="Primary", password_hash=password, role="reviewer", enabled=True)
        secondary = User(username="secondary", display_name="Secondary", password_hash=password, role="reviewer", enabled=True)
        adjudicator = User(username="adjudicator", display_name="Adjudicator", password_hash=password, role="developer", enabled=True)
        session.add_all([owner, primary, secondary, adjudicator])
        session.flush()
        session.add(SystemSetting(key="owner_user_id", value=owner.user_id))
        item1 = add_review_item(session, "browser-item-1", case_id="case-a", namespace="pilot", item_type="conflict_pair")
        item2 = add_review_item(session, "browser-item-2", case_id="case-b", namespace="pilot", item_type="fulltext_l1_claim")
        project = EvaluationProject(name="Browser Pilot", namespace="pilot", status="active", created_by_user_id=owner.user_id)
        session.add(project)
        session.flush()
        for role, reviewer, item in (("primary", primary, item1), ("secondary", secondary, item1), ("adjudicator", adjudicator, item1), ("primary", primary, item2), ("secondary", secondary, item2), ("adjudicator", adjudicator, item2)):
            session.add(Assignment(project_id=project.project_id, review_item_id=item.review_item_id, reviewer_user_id=reviewer.user_id, assignment_role=role, status="assigned", assigned_by_user_id=owner.user_id))
    app = create_app(root, None, require_auth=True, secret_key="browser-test-secret", database_url=url, require_database=True, testing=False)
    app.run(host="127.0.0.1", port=int(os.environ.get("ATLAS_E2E_PORT", "18765")), debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
