# OpenHAB MCP Server

A MCP (Model Context Protocol) server that interacts with a real openHAB instance.

## Overview

This project provides an implementation of an MCP server that connects to a real openHAB instance via its REST API. It enables AI assistants like Claude and Cline to interact with your openHAB smart home system.

The server provides comprehensive access to openHAB's core components:

### Items

- List, get, create, update, and delete items
- Update item states

### Things

- List all things
- Get, create, update, and delete things
- Update thing configurations
- Get thing configuration status
- Set thing enabled/disabled status
- Get thing status and firmware information
- Get available firmware updates

### Rules

- List, get, create, update, and delete rules
- Update rule script actions
- Run rules on demand

### Scripts

- List, get, create, update, and delete scripts

When connected to Claude or Cline in VSCode, you can use natural language to control and manage your openHAB system, making home automation more accessible and intuitive.

## Requirements

- Python 3.7+

## Quick Start (prebuilt image)

The official image is published to the GitHub Container Registry (`ghcr.io/tdeckers/openhab-mcp`). Pulling this image is the fastest way to get the MCP server running.

By default the server uses stdio for MCP. For remote HTTP clients, Streamable HTTP is preferred (`MCP_TRANSPORT=http`) and exposes `http://HOST:PORT/mcp`. SSE is still supported for backwards compatibility at `http://HOST:PORT/sse` (`MCP_TRANSPORT=sse`). The container examples below use Streamable HTTP; for stdio, omit `MCP_TRANSPORT` and the port mapping. Streamable HTTP supports session headers like `Mcp-Session-Id` for stateful clients.

1. (Optional for private registries) Authenticate with GHCR:

   ```bash
   podman login ghcr.io
   # or: docker login ghcr.io
   ```

2. Run the container with Podman (add `-e OPENHAB_USERNAME=...` and `-e OPENHAB_PASSWORD=...` if your OpenHAB instance requires basic authentication):

   ```bash
   podman run -d --rm -p 8081:8000 \
     -e MCP_TRANSPORT=http \
     -e OPENHAB_URL=http://your-openhab-host:8080 \
     -e OPENHAB_API_TOKEN=your-api-token \
     --name openhab-mcp \
     ghcr.io/tdeckers/openhab-mcp:latest

   ```

   Using Docker instead?

   ```bash
   docker run -d --rm -p 8081:8000 \
     -e MCP_TRANSPORT=http \
     -e OPENHAB_URL=http://your-openhab-host:8080 \
     -e OPENHAB_API_TOKEN=your-api-token \
     --name openhab-mcp \
     ghcr.io/tdeckers/openhab-mcp:latest
   ```

3. Stop the container when you are done:

   ```bash
   podman stop openhab-mcp
   # or: docker stop openhab-mcp
   ```

When running with `MCP_TRANSPORT=http` (Streamable HTTP) or `MCP_TRANSPORT=sse`, the container listens on port 8000 internally, but the examples map it to port 8081 on the host to avoid conflicts with an existing OpenHAB installation. Streamable HTTP clients connect to `http://HOST:PORT/mcp`, while SSE clients connect to `http://HOST:PORT/sse`.

## Optional: Build and run a custom image

If you need to modify the code, build and tag the image locally instead:

1. Build the image:

   ```bash
   make docker-build
   # or directly: podman build -t openhab-mcp .
   ```

2. Run your custom image:

   ```bash
   make docker-run
   # or directly:
   podman run -d --rm -p 8081:8000 \
     -e MCP_TRANSPORT=http \
     -e OPENHAB_URL=http://your-openhab-host:8080 \
     -e OPENHAB_API_TOKEN=your-api-token \
     --name openhab-mcp \
     openhab-mcp
   ```

   Ensure the `OPENHAB_URL`, `OPENHAB_API_TOKEN`, and optional `OPENHAB_USERNAME`/`OPENHAB_PASSWORD` variables are set in your shell before invoking `make docker-run`.

3. Stop the custom container:

   ```bash
   make docker-stop
   # or directly: podman stop openhab-mcp
   ```

## Using with Claude and Cline in VSCode

You can connect this OpenHAB MCP server to Claude or Cline in VSCode to interact with your OpenHAB instance through AI assistants.

### Prerequisites

- For Claude: [Claude Desktop app](https://claude.ai/desktop) installed
- For Cline: [Cline VSCode extension](https://marketplace.visualstudio.com/items?itemName=Anthropic.cline) installed

### Configuration for Claude Desktop

1. Run the container using the steps in "Quick Start" (published image) or "Optional: Build and run a custom image".
2. Create a configuration file for Claude Desktop:

Save the following as `claude_desktop_config.json` in your Claude Desktop configuration directory:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcp_servers": [
    {
      "name": "openhab-mcp",
      "command": "podman",
      "args": [
        "run",
        "-d",
        "-p",
        "8081:8000",
        "-e",
        "MCP_TRANSPORT=http",
        "-e",
        "OPENHAB_URL=http://your-openhab-host:8080",
        "-e",
        "OPENHAB_API_TOKEN=your-api-token",
        "--name",
        "openhab-mcp",
        "ghcr.io/tdeckers/openhab-mcp:latest"
      ]
    }
  ]
}
```

### Configuration for Cline in VSCode

1. Run the container using the steps in "Quick Start" (published image) or "Optional: Build and run a custom image".
2. Create a configuration file for Cline:

Save the following as `mcp.json` in your Cline configuration directory:

- macOS/Linux: `~/.cursor/mcp.json`
- Windows: `%USERPROFILE%\.cursor\mcp.json`

```json
{
  "mcp_servers": [
    {
      "name": "openhab-mcp",
      "command": "podman",
      "args": [
        "run",
        "-d",
        "-p",
        "8081:8000",
        "-e",
        "MCP_TRANSPORT=http",
        "-e",
        "OPENHAB_URL=http://your-openhab-host:8080",
        "-e",
        "OPENHAB_API_TOKEN=your-api-token",
        "--name",
        "openhab-mcp",
        "ghcr.io/tdeckers/openhab-mcp:latest"
      ]
    }
  ]
}
```

### Restart and Verify

1. After creating the configuration file, restart Claude Desktop or VSCode
2. Open a new conversation with Claude or Cline
3. You should now be able to interact with your OpenHAB instance through the AI assistant

Example prompt to test the connection:

```
Can you list all the items in my OpenHAB system?
```

If configured correctly, Claude/Cline will use the MCP server to fetch and display your OpenHAB items.

### Transport Endpoints (Streamable HTTP vs SSE)

- **Streamable HTTP (preferred):** set `MCP_TRANSPORT=http` and connect to `http://HOST:PORT/mcp`
- **SSE (backwards compatible):** set `MCP_TRANSPORT=sse` and connect to `http://HOST:PORT/sse`

If a Streamable HTTP client POSTs to `/sse`, the server returns `405 Method Not Allowed` because `/sse` only accepts SSE GET/subscribe requests.

## Transport Smoke Test

Use these quick checks after deployment:

- **Streamable HTTP (preferred)**
  - Ensure `MCP_TRANSPORT=http` is set.
  - Initialize with a POST to `/mcp` (client libraries handle this automatically).
  - Manual probe (expects `405` for GET; POST should succeed):

    ```bash
    curl -i http://HOST:PORT/mcp
    ```

- **SSE (backwards compatible)**
  - Ensure `MCP_TRANSPORT=sse` is set.
  - The SSE endpoint accepts GET at `/sse` for subscriptions.
  - Manual probe (expects an SSE stream):

    ```bash
    curl -i http://HOST:PORT/sse
    ```

## MCP Tools

The server provides the following tools:

### Item Management

1. `list_items` - Paginated list of openHAB items with optional tag, type, name, and label filters
2. `get_item` - Get a specific openHAB item by name
3. `create_item` - Create a new openHAB item
4. `update_item` - Update an existing openHAB item
5. `delete_item` - Delete an openHAB item
6. `update_item_state` - Update just the state of an openHAB item

### Thing Management

1. `list_things` - Paginated list of openHAB things with optional UID and label filters
2. `get_thing` - Get a specific openHAB thing by UID
3. `create_thing` - Create a new openHAB thing
4. `update_thing` - Update an existing openHAB thing
5. `delete_thing` - Delete an openHAB thing
6. `update_thing_config` - Update an openHAB thing's configuration
7. `get_thing_config_status` - Get openHAB thing configuration status
8. `set_thing_enabled` - Set the enabled status of an openHAB thing
9. `get_thing_status` - Get openHAB thing status
10. `get_thing_firmware_status` - Get openHAB thing firmware status
11. `get_available_firmwares` - Get available firmwares for an openHAB thing

### Rule Management

1. `list_rules` - List all openHAB rules, optionally filtered by tag
2. `get_rule` - Get a specific openHAB rule by UID
3. `create_rule` - Create a new openHAB rule
4. `update_rule` - Update an existing openHAB rule with partial updates
5. `update_rule_script_action` - Update a script action in an openHAB rule
6. `delete_rule` - Delete an openHAB rule
7. `run_rule_now` - Run an openHAB rule immediately

### Script Management

1. `list_scripts` - List all openHAB scripts (rules with tag 'Script' and no trigger)
2. `get_script` - Get a specific openHAB script by ID
3. `create_script` - Create a new openHAB script
4. `update_script` - Update an existing openHAB script
5. `delete_script` - Delete an openHAB script

### Link Management

1. `list_links` - List all openHAB item-channel links, optionally filtered by channel UID or item name
2. `get_link` - Get a specific openHAB item-channel link
3. `create_or_update_link` - Create or update an openHAB item-channel link
4. `delete_link` - Delete a specific openHAB item-channel link
5. `get_orphan_links` - Get orphaned openHAB item-channel links (links to non-existent channels)
6. `purge_orphan_links` - Remove all orphaned openHAB item-channel links
7. `delete_all_links_for_object` - Delete all openHAB links for a specific item or thing

## MCP Resources

The server provides the following resources:

1. `openhab://items` - List of all items in the openHAB system
2. `openhab://items/{item_name}` - Get a specific item by name

## Sample Item Structure

```json
{
  "name": "LivingRoom_Light",
  "type": "Switch",
  "label": "Living Room Light",
  "state": "OFF",
  "tags": ["Lighting", "LivingRoom"],
  "groups": ["gLights", "gLivingRoom"]
}
```

## Development

For development purposes, please refer to the DEVELOPER.md file for more information on the Podman-based development workflow.

## Notes

This implementation connects to a real openHAB instance via its REST API. For production use, you might want to enhance it with:

1. More comprehensive error handling and logging
2. Additional authentication and security features
3. More sophisticated caching mechanisms
4. Support for more openHAB features (rules, things, etc.)

## License

MIT
