"""Guarded uniprot request planner."""

from code_engine.validation.clients.guarded_http import GuardedRemoteClient


class UniProtClient(GuardedRemoteClient):
    name = "uniprot"
    endpoint = "https://rest.uniprot.org"


__all__ = ["UniProtClient"]
