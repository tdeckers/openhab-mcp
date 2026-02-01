# AGENTS.md

## Purpose
This repo is an MCP server that talks to a real openHAB instance over its REST API. It can run as a local Python app or in a Podman/Docker container. There are smoke tests under `tests/`.

## Key files
- `openhab_mcp_server.py`: MCP server entrypoint (`openhab-mcp` console script).
- `openhab_client.py`: REST client for openHAB.
- `models.py`: Pydantic models.
- `docker-compose.yml`: Dev env (openHAB + MCP) via podman-compose.
- `Makefile`: Container build/run/dev commands.

## Common commands
- Install deps: `uv sync` (add `--extra dev` for dev tools)
- Run tests: `uv run pytest`
- Lint/format (dev extras): `uv run flake8`, `uv run isort .`, `uv run black .`
- Build container: `make docker-build`
- Run container: `make docker-run` (requires `OPENHAB_URL`/`OPENHAB_API_TOKEN` env vars)
- Dev env: `make dev-env` (podman-compose)

## Runtime notes
- Streamable HTTP transport is preferred: set `MCP_TRANSPORT=http` and use `http://HOST:PORT/mcp`.
- SSE is still supported: set `MCP_TRANSPORT=sse` and use `http://HOST:PORT/sse`.
- Default MCP container examples map `8000` inside to `8081` on host.

## Testing notes
- Use `uv run` for local commands to ensure the locked environment is used.
- Tests may require a reachable openHAB instance; if failing locally, verify `OPENHAB_URL` and `OPENHAB_API_TOKEN`.

## Style
- Python formatting: Black (88 columns) and isort.
- Lint rules: flake8 with `E203,W503` ignored.
