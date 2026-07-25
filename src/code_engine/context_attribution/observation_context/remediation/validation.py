from .models import ObservationContextRemediationNeedV1
VALIDATOR="observation_context_remediation_need_validator_v1"
def validate_need(value:ObservationContextRemediationNeedV1)->list[str]:
    return [] if value.active and value.remediation_status in {"open","blocked_policy_review","blocked_missing_source"} else ["inactive_or_invalid_status"]
