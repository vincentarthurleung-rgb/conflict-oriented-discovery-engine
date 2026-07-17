from __future__ import annotations

import os
import tempfile
from pathlib import Path

from code_engine.system_b.explorer.auth import hash_password
from code_engine.system_b.explorer.explorer_server import create_app
from code_engine.system_b.persistence.database import create_atlas_engine, session_factory, session_scope
from code_engine.system_b.persistence.models import SystemSetting, User
from code_engine.system_b.persistence.services.assignment_service import create_project_with_assignments
from tests.atlas_db_test_utils import add_review_item, migrate
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests


def main() -> None:
    tmp = tempfile.TemporaryDirectory()
    project_root = Path(__file__).resolve().parents[2]
    root = Path(os.environ.get("ATLAS_DISPLAY_ROOT") or project_root / "system_b_outputs" / "system_a_sync")
    if not (root / "current_projection.json").is_file():
        # Keep the browser harness runnable in a minimal source checkout.
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
        create_project_with_assignments(
            session,
            owner={"user_id": owner.user_id, "username": owner.username, "role": "owner"},
            name="Browser Pilot",
            namespace="pilot",
            annotation_schema_version="atlas_annotation_v1",
            primary_reviewer_user_id=primary.user_id,
            secondary_reviewer_user_id=secondary.user_id,
            adjudicator_user_id=adjudicator.user_id,
            batch_size=1,
            item_ids=[item1.review_item_id],
        )
    app = create_app(root, None, require_auth=True, secret_key="browser-test-secret", allow_registration=True, database_url=url, require_database=True, testing=False)
    app.run(host="127.0.0.1", port=int(os.environ.get("ATLAS_E2E_PORT", "18765")), debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
