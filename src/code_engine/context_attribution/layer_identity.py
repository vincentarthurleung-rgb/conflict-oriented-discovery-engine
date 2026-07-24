from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def layer_identity(kind: str, version: str, payload: dict[str, Any]) -> str:
    envelope = {"identity_kind": kind, "identity_version": version, **payload}
    return hashlib.sha256(canonical_json(envelope).encode("utf-8")).hexdigest()
