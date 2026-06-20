import importlib
import sys

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient


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


def test_remote_app_disables_trailing_slash_redirects(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("MCP_MODE", "remote")

    module = _load_module()
    app = module._build_remote_app()

    assert app.router.redirect_slashes is False
    for route in app.routes:
        child_app = getattr(route, "app", None)
        child_router = getattr(child_app, "router", None)
        if child_router is not None:
            assert child_router.redirect_slashes is False


def test_transport_routes_accept_slashless_and_slash_paths_without_redirect(
    monkeypatch,
):
    _set_base_env(monkeypatch)
    module = _load_module()

    async def child_root(request):
        return PlainTextResponse(request.scope["path"])

    child_app = Starlette(routes=[Route("/", child_root)])
    app = Starlette(routes=module._transport_routes("/example", child_app))
    app.router.redirect_slashes = False

    with TestClient(app, follow_redirects=False) as client:
        slashless_response = client.get("/example")
        slash_response = client.get("/example/")

    assert slashless_response.status_code == 200
    assert slashless_response.text == "/"
    assert "location" not in slashless_response.headers

    assert slash_response.status_code == 200
    assert "location" not in slash_response.headers
