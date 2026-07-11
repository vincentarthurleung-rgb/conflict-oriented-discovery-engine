import os
from pathlib import Path

from alembic import command
from alembic.config import Config

from code_engine.system_b.explorer.auth import hash_password
from code_engine.system_b.persistence.database import create_atlas_engine, session_factory
from code_engine.system_b.persistence.models import ReviewItem, User
from code_engine.system_b.persistence.services.review_service import canonical_json, sha256_text
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests, write_jsonl


def migrate(url: str) -> None:
    os.environ["ATLAS_DATABASE_URL"] = url
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


def session_for(url: str):
    engine = create_atlas_engine(url)
    return session_factory(engine)


def add_user(session, username: str, role: str = "reviewer", enabled: bool = True) -> User:
    user = User(username=username, display_name=username.title(), password_hash=hash_password("correct horse battery staple"), role=role, enabled=enabled)
    session.add(user)
    session.flush()
    return user


def add_review_item(session, item_id: str = "item1", case_id: str = "case1", namespace: str = "production", item_type: str = "fulltext_l1_claim") -> ReviewItem:
    payload = {"review_item_id": item_id, "case_id": case_id, "item_type": item_type, "evidence_sentence": "A promotes B."}
    raw = canonical_json(payload)
    item = ReviewItem(review_item_id=item_id, case_id=case_id, item_type=item_type, payload_json=raw, source_hash=sha256_text(raw), import_run_id="test", namespace=namespace)
    session.add(item)
    session.flush()
    return item


def atlas_fixture(root: Path, review: Path, item_id: str = "item1") -> None:
    root.mkdir(parents=True, exist_ok=True)
    KnowledgeExplorerTests().fixture(root)
    review.mkdir(parents=True, exist_ok=True)
    write_jsonl(review / "manual_review_queue.jsonl", [{"review_item_id": item_id, "case_id": "case1", "item_type": "fulltext_l1_claim", "evidence_sentence": "A promotes B."}])
