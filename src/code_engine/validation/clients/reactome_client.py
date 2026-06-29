"""Guarded reactome request planner."""

from code_engine.validation.clients.guarded_http import GuardedRemoteClient


class ReactomeClient(GuardedRemoteClient):
    name = "reactome"
    endpoint = "https://reactome.org/ContentService"


__all__ = ["ReactomeClient"]
