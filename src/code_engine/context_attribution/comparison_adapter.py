from __future__ import annotations

from copy import deepcopy
from typing import Any

from .identities import canonical_sha256
from .models import ContextPairAttributionV3

PAIR_V2_TO_V3_ADAPTER_VERSION = (
    "context_pair_attribution_v2_to_v3_missing_value_adapter_v1"
)


def adapt_pair_v2_to_v3(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = deepcopy(payload)
    adapted = deepcopy(payload)
    adapted["schema_version"] = "context_pair_attribution_v3"
    # Deliberately no value, status, confidence, or comparability edits.
    ContextPairAttributionV3.model_validate(adapted)
    audit = {
        "adapter_version": PAIR_V2_TO_V3_ADAPTER_VERSION,
        "source_schema_version": source.get("schema_version"),
        "target_schema_version": adapted["schema_version"],
        "source_payload_sha256": canonical_sha256(source),
        "adapted_payload_sha256": canonical_sha256(adapted),
        "before_after_canonical_diff": {
            "schema_version": [source.get("schema_version"), adapted["schema_version"]],
        },
        "values_created": False,
        "factor_comparison_content_modified": False,
        "comparability_modified": False,
        "confidence_modified": False,
    }
    return adapted, audit
