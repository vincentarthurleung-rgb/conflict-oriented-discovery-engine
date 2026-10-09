"""Trusted R2 construction only; never repairs a serialized observation."""

import platform
from dataclasses import dataclass
from pathlib import Path

from . import append_only_attempt_journal_v1 as u

SCHEMA_SHA256 = "47b881c7e6432aec67e7ba37779be94d6f0e7a159d432f364153484132799076"
RUNTIME_ACTIVATION_ALLOWED = False


def exception_schema():
    path = Path(__file__).resolve().parents[2] / "runs/20261008_search_plan_v24_dev_alpha3_22a_transport_state_observability_implementation_offline/exception_provenance_v1_schema.json"
    raw = u.read_bytes(path)
    u.require(u.sha(raw) == SCHEMA_SHA256, "FROZEN_RUNTIME_IDENTITY_SCHEMA_DRIFT")
    return u.strict_json(raw)


@dataclass(frozen=True)
class FrozenRuntimeIdentityR2:
    serialized: bytes

    def __post_init__(self):
        record = u.strict_json(self.serialized)
        u.o.validate_schema(record, exception_schema()["properties"]["runtime_identity"])
        u.require(u.canonical(record) == self.serialized, "NONCANONICAL_RUNTIME_IDENTITY")

    def record(self):
        # Consumers receive a new dictionary, never the trusted stored bytes.
        return u.strict_json(self.serialized)


def capture_runtime_identity(redactor):
    """Capture the existing 22A interpreter convention exactly once per event."""
    u.require(type(redactor) is u.o.SecretRedactorV1, "VERSIONED_REDACTOR_REQUIRED")
    version = platform.python_version()
    u.require(type(version) is str and bool(version.strip()) and version.lower() not in {"unknown", "unavailable"},
              "RUNTIME_PYTHON_VERSION_UNAVAILABLE")
    record = {"python_version": version, "client_module": "urllib.request/http.client.HTTPResponse",
              "client_version": None, "client_code_sha256": u.b.BOUND_CLIENT_IDENTITY_SHA256}
    clean, _ = redactor.tree(record)
    return FrozenRuntimeIdentityR2(u.canonical(clean))
