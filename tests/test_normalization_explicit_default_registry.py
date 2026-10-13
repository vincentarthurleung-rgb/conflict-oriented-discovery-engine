"""Explicit registry paths must be honored, including the default filename."""
import json
import socket
from pathlib import Path

import pytest

from code_engine.normalization.registry import DEFAULT_REGISTRY_PATH, PILOT_REGISTRY_PATH
from code_engine.normalization.resolver import ResolverCascade

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("NETWORK_FORBIDDEN")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


def test_explicit_default_filename_loads_only_explicit_fixture(tmp_path, monkeypatch):
    # A physical copy of an existing test fixture, never a production mapping.
    fixture = (ROOT / PILOT_REGISTRY_PATH).read_bytes()
    monkeypatch.chdir(tmp_path)
    DEFAULT_REGISTRY_PATH.parent.mkdir(parents=True)
    DEFAULT_REGISTRY_PATH.write_bytes(fixture)
    resolver = ResolverCascade(registry_path=DEFAULT_REGISTRY_PATH, external_clients={})
    assert [type(p).__name__ for p in resolver.hub.providers] == ["LocalCuratedProvider", "NullProvider"]
    result = resolver.resolve_entity("ketamine")
    assert result.normalization_status == "resolved"
    assert result.canonical_id == "CHEM:KETAMINE"


def test_implicit_default_does_not_autoload_populated_fixture(tmp_path, monkeypatch):
    fixture = (ROOT / PILOT_REGISTRY_PATH).read_bytes()
    monkeypatch.chdir(tmp_path)
    DEFAULT_REGISTRY_PATH.parent.mkdir(parents=True)
    DEFAULT_REGISTRY_PATH.write_bytes(fixture)
    resolver = ResolverCascade(external_clients={})
    assert [type(p).__name__ for p in resolver.hub.providers] == ["LocalCacheProvider", "NullProvider"]
    assert resolver.resolve_entity("ketamine").normalization_status == "unresolved_fallback"


def test_explicit_missing_default_registry_fails_instead_of_silently_skipping(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match="registry missing"):
        ResolverCascade(registry_path=DEFAULT_REGISTRY_PATH, external_clients={})


def test_explicit_empty_default_stays_empty(tmp_path, monkeypatch):
    actual = (ROOT / DEFAULT_REGISTRY_PATH).read_bytes()
    assert json.loads(actual)["entities"] == []
    monkeypatch.chdir(tmp_path)
    DEFAULT_REGISTRY_PATH.parent.mkdir(parents=True)
    DEFAULT_REGISTRY_PATH.write_bytes(actual)
    resolver = ResolverCascade(registry_path=DEFAULT_REGISTRY_PATH, external_clients={})
    assert [type(p).__name__ for p in resolver.hub.providers] == ["LocalCuratedProvider", "NullProvider"]
    result = resolver.resolve_entity("androgen receptor")
    assert result.normalization_status == "unresolved_fallback" and not result.canonical_id
