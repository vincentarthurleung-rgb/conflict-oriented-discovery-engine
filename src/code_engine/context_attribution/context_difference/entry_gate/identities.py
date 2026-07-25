from ...layer_identity import layer_identity

def identity(kind: str, payload: dict) -> str:
    return layer_identity(kind, f"{kind}_identity_v1", payload)
