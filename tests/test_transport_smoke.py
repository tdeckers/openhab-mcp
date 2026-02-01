import importlib
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


def test_mode_defaults_to_stdio(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.delenv("MCP_MODE", raising=False)
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)

    module = _load_module()

    assert module.MCP_MODE == "stdio"


def test_mode_remote_explicit(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("MCP_MODE", "remote")

    module = _load_module()

    assert module.MCP_MODE == "remote"


def test_mode_invalid_falls_back_to_stdio(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("MCP_MODE", "nope")

    module = _load_module()

    assert module.MCP_MODE == "stdio"


def test_transport_aliases_to_remote(monkeypatch):
    _set_base_env(monkeypatch)

    for value in ("http", "streamable-http", "streamable_http", "sse"):
        monkeypatch.delenv("MCP_MODE", raising=False)
        monkeypatch.setenv("MCP_TRANSPORT", value)
        module = _load_module()
        assert module.MCP_MODE == "remote"


def test_transport_invalid_does_not_change_default(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("MCP_TRANSPORT", "nope")

    module = _load_module()

    assert module.MCP_MODE == "stdio"


def test_mode_overrides_transport(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("MCP_MODE", "remote")
    monkeypatch.setenv("MCP_TRANSPORT", "nope")

    module = _load_module()

    assert module.MCP_MODE == "remote"
