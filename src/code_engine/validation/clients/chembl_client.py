"""Guarded chembl request planner."""

from code_engine.validation.clients.guarded_http import GuardedRemoteClient


class ChEMBLClient(GuardedRemoteClient):
    name = "chembl"
    endpoint = "https://www.ebi.ac.uk/chembl/api/data"


__all__ = ["ChEMBLClient"]
