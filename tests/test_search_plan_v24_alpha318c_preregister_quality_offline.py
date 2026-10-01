"""Read-only checks for the prospective Quality preregistration."""
from __future__ import annotations

import json

import pytest

from scripts import search_plan_v24_alpha318c_preregister_quality_offline as prereg


def test_frozen_inputs_and_output_root() -> None:
    candidates, groups, requests = prereg.verify_upstream()
    assert (len(candidates), len(groups), len(requests)) == (5, 3, 3)
    assert prereg.root(prereg.OUT, prereg.ROOT_MARKER) == (
        prereg.OUT / prereg.ROOT_MARKER).read_text().strip()


def test_provider_projection_preserves_scientific_messages() -> None:
    requests = prereg.rows(prereg.B2 / "proposition_quality_v2_request_manifest_v3.jsonl")
    verification = json.loads((prereg.OUT / "quality_request_manifest_verification.json").read_text())
    for frozen, projected in zip(requests, verification["model_projection_only_at_provider_serialization"]):
        request = dict(frozen["request"])
        request["model"] = prereg.MODEL
        assert projected["frozen_request_sha256"] == frozen["request_sha256"]
        assert projected["provider_serialized_request_sha256"] == prereg.sha(prereg.canonical(request))
        assert projected["messages_sha256"] == prereg.sha(prereg.canonical(frozen["request"]["messages"]))


def test_frozen_request_hash_mismatch_fails_closed() -> None:
    requests = prereg.rows(prereg.B2 / "proposition_quality_v2_request_manifest_v3.jsonl")
    altered = dict(requests[0]["request"])
    altered["model"] = prereg.MODEL
    assert prereg.sha(prereg.canonical(altered)) != requests[0]["request_sha256"]
    with pytest.raises(RuntimeError, match="QUALITY_REQUEST_FREEZE_MISMATCH"):
        prereg.require(False, "QUALITY_REQUEST_FREEZE_MISMATCH")
