"""Stage A: trusted construction only, before the six identity negatives."""

from unittest.mock import patch

import pytest

from scripts import search_plan_v24_alpha322r2_runtime_identity_fixtures as ri


@pytest.fixture(autouse=True)
def offline():
    with ri.h.r0.d.master.prior.offline_guard():
        yield


def test_actual_interpreter_exact_fields_types_and_schema():
    result = ri.construction()
    assert result["passed"] and all(result["checks"].values())
    assert result["python_version_capture_calls"] == 1


@pytest.mark.parametrize("value", [None, "", " ", "unknown", "unavailable"])
def test_unavailable_interpreter_fails_closed_no_fabricated_default(value):
    with patch.object(ri.identity.platform, "python_version", return_value=value):
        with pytest.raises(ri.t.TransportContractError, match="RUNTIME_PYTHON_VERSION_UNAVAILABLE"):
            ri.identity.capture_runtime_identity(ri.o.SecretRedactorV1())


def test_frozen_identity_copies_do_not_mutate_capture():
    identity = ri.identity.capture_runtime_identity(ri.o.SecretRedactorV1())
    original = identity.record()
    consumer_copy = identity.record()
    consumer_copy.pop("python_version")
    assert identity.record() == original
    with pytest.raises(ri.t.TransportContractError, match="SCHEMA_REQUIRED"):
        ri.identity.FrozenRuntimeIdentityR2(ri.j.canonical(consumer_copy))
