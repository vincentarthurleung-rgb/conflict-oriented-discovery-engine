"""Guarded pubchem request planner."""

from code_engine.validation.clients.guarded_http import GuardedRemoteClient


class PubChemClient(GuardedRemoteClient):
    name = "pubchem"
    endpoint = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


__all__ = ["PubChemClient"]
