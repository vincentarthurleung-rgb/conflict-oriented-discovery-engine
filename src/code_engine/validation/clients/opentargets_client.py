"""Guarded opentargets request planner."""

from code_engine.validation.clients.guarded_http import GuardedRemoteClient


class OpenTargetsClient(GuardedRemoteClient):
    name = "opentargets"
    endpoint = "https://api.platform.opentargets.org/api/v4/graphql"


__all__ = ["OpenTargetsClient"]
