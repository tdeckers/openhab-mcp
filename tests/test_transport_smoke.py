import importlib
import os
import sys


def _load_module():
    if "openhab_mcp_server" in sys.modules:
        del sys.modules["openhab_mcp_server"]
    return importlib.import_module("openhab_mcp_server")


def _set_base_env(monkeypatch):
    # Avoid noisy warnings about missing credentials.
    monkeypatch.setenv("OPENHAB_API_TOKEN", "test-token")
    monkeypatch.delenv("OPENHAB_USERNAME", raising=False)
    monkeypatch.delenv("OPENHAB_PASSWORD", raising=False)


def test_transport_defaults_to_stdio(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)

    module = _load_module()

    assert module.MCP_TRANSPORT == "stdio"


def test_transport_http_aliases_to_streamable_http(monkeypatch):
    _set_base_env(monkeypatch)

    for value in ("http", "streamable-http", "streamable_http"):
        monkeypatch.setenv("MCP_TRANSPORT", value)
        module = _load_module()
        assert module.MCP_TRANSPORT == "streamable-http"


def test_transport_sse_kept(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("MCP_TRANSPORT", "sse")

    module = _load_module()

    assert module.MCP_TRANSPORT == "sse"


def test_transport_invalid_falls_back_to_stdio(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("MCP_TRANSPORT", "nope")

    module = _load_module()

    assert module.MCP_TRANSPORT == "stdio"
