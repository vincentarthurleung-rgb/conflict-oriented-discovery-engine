from .models import ObservationContextRemediationNeedV1
def assert_unique_active(needs:list[ObservationContextRemediationNeedV1])->None:
    ids=[x.observation_id for x in needs if x.active]
    if len(ids)!=len(set(ids)): raise ValueError("duplicate_active_observation_remediation")
