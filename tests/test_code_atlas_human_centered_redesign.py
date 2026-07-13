import tempfile
from pathlib import Path

from code_engine.system_b.explorer.explorer_api import ExplorerAPI
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests, write_jsonl


def _api():
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    KnowledgeExplorerTests().fixture(root)
    api = ExplorerAPI(root, root / "missing-review-root")
    api._test_tmp = tmp
    return api, root


def test_case_contract_explains_capabilities_and_next_level_metadata():
    api, _ = _api()
    case = api.dispatch("/api/cases")[1]["items"][0]
    assert case["display_name"]
    assert case["research_question"]
    assert set(case["capabilities"]) == {"fulltext", "reasoning", "context", "reentry"}
    assert case["capabilities"]["reasoning"] in {"available", "partial", "unavailable"}
    assert "formal_conflict_count" in case
    assert "paper_count" in case


def test_context_matrix_keeps_source_layers_and_simplified_columns():
    api, root = _api()
    triple = api.triples[0]
    write_jsonl(root / "triple_contexts.jsonl", [{
        "triple_id": triple["triple_id"], "case_id": "case", "pmid": "1",
        "evidence_sentence": "A affects B", "species": "mouse",
    }])
    write_jsonl(root / "triple_evidence_links.jsonl", [{
        "triple_id": triple["triple_id"], "case_id": "case", "pmid": "1",
        "evidence_sentence": "A affects B", "source_scope": "fulltext",
        "context": {"species": "human", "treatment": "drug"},
    }])
    api = ExplorerAPI(root, root / "missing-review-root")
    dossier_id = api.dossiers.resolve(triple["triple_id"])
    matrix = api.dispatch(f"/api/dossier/{dossier_id}/context-matrix")[1]
    row = matrix["items"][0]
    assert row["species"] == "冲突值"
    assert row["context_provenance"]["species"] == "conflicting"
    assert {x["source_layer"] for x in row["context_source_values"]["species"]} == {"claim-derived", "consolidated"}
    assert "paper_title" in matrix["simple_columns"]


def test_reasoning_unavailable_is_explicit_and_does_not_infer_steps():
    api, _ = _api()
    dossier_id = api.dossiers.resolve(api.triples[0]["triple_id"])
    reasoning = api.dispatch(f"/api/dossier/{dossier_id}/reasoning")[1]
    assert reasoning["status"] == "unavailable"
    assert reasoning["items"] == []
    assert reasoning["missing_message"] == "该运行未生成全文推理证据链。"


def test_normal_user_views_gate_raw_details_by_developer_permission():
    js = Path("src/code_engine/system_b/explorer/static/app.js").read_text(encoding="utf-8")
    assert "if(!isDeveloperMode())return\"\"" in js
    assert "技术详情：标识、投影与来源" in js
    assert "实验推理证据链当前不可用" in js
    assert "提交判断并进入下一条" in js
