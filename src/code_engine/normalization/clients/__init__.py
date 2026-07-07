"""Entity resolution HTTP clients for external knowledge bases."""

from __future__ import annotations

from code_engine.normalization.clients.mygene_client import MyGeneClient
from code_engine.normalization.clients.uniprot_client import UniProtClient
from code_engine.normalization.clients.pubchem_client import PubChemClient
from code_engine.normalization.clients.chembl_client import ChEMBLClient


def create_default_clients() -> dict[str, object]:
    """Create default entity resolution clients keyed by provider name."""
    return {
        "mygene": MyGeneClient(),
        "uniprot": UniProtClient(),
        "pubchem": PubChemClient(),
        "chembl": ChEMBLClient(),
    }


__all__ = [
    "MyGeneClient",
    "UniProtClient",
    "PubChemClient",
    "ChEMBLClient",
    "create_default_clients",
]
