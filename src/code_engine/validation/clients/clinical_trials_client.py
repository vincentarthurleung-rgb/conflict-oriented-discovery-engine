"""Guarded clinical_trials request planner."""

from code_engine.validation.clients.guarded_http import GuardedRemoteClient


class ClinicalTrialsClient(GuardedRemoteClient):
    name = "clinical_trials"
    endpoint = "https://clinicaltrials.gov/api/v2"


__all__ = ["ClinicalTrialsClient"]
