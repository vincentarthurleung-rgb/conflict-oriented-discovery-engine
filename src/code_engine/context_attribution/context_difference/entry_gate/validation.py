from .models import ContextDifferenceEntryAuthorizationV1, ContextDifferenceAuthorityV1

ENTRY_VALIDATOR = "context_difference_entry_authorization_validator_v1"

def validate_entry(value: ContextDifferenceEntryAuthorizationV1) -> list[str]:
    return [] if value.ready_for_authoritative_context_difference == (value.entry_status == "ready") else ["ready_flag_mismatch"]

def validate_difference_authority(value: ContextDifferenceAuthorityV1) -> list[str]:
    return [] if not value.source_payload_modified else ["source_payload_modified"]
