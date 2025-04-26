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
- Get specific things by UID

### Rules
- List, get, create, update, and delete rules
- Update rule script actions
- Run rules on demand

### Scripts
- List, get, create, update, and delete scripts

When connected to Claude or Cline in VSCode, you can use natural language to control and manage your openHAB system, making home automation more accessible and intuitive.

## Requirements

- Python 3.7+

## Installation and Usage

The recommended way to run the OpenHAB MCP Server is using Docker:

To run the MCP using Docker, follow these steps:

1. Build the Docker image:
   ```bash
   make docker-build
   # or directly: docker build -t openhab-mcp .
   ```

2. Run the Docker container:
   ```bash
   make docker-run
   # or directly:
   docker run -d --rm -p 8081:8080 \
     -e OPENHAB_URL=http://your-openhab-host:8080 \
     -e OPENHAB_API_TOKEN=your-api-token \
     --name openhab-mcp \
     openhab-mcp
   ```

3. To stop the container:
   ```bash
   make docker-stop
   # or directly: docker stop openhab-mcp
   ```

Note: The container exposes port 8080 internally, but we map it to port 8081 on the host to avoid conflicts with OpenHAB which typically uses port 8080.

## Using with Claude and Cline in VSCode

You can connect this OpenHAB MCP server to Claude or Cline in VSCode to interact with your OpenHAB instance through AI assistants.

### Prerequisites

- For Claude: [Claude Desktop app](https://claude.ai/desktop) installed
- For Cline: [Cline VSCode extension](https://marketplace.visualstudio.com/items?itemName=Anthropic.cline) installed

### Configuration for Claude Desktop

1. Build and run the Docker container as described in the "Running the MCP with Docker" section.
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
      "command": "docker",
      "args": [
        "run",
        "-d",
        "-p",
        "8081:8080",
        "-e",
        "OPENHAB_URL=http://your-openhab-host:8080",
        "-e",
        "OPENHAB_API_TOKEN=your-api-token",
        "--name",
        "openhab-mcp",
        "openhab-mcp"
      ]
    }
  ]
}
```

### Configuration for Cline in VSCode

1. Build and run the Docker container as described in the "Running the MCP with Docker" section.
2. Create a configuration file for Cline:

Save the following as `mcp.json` in your Cline configuration directory:

- macOS/Linux: `~/.cursor/mcp.json`
- Windows: `%USERPROFILE%\.cursor\mcp.json`

```json
{
  "mcp_servers": [
    {
      "name": "openhab-mcp",
      "command": "docker",
      "args": [
        "run",
        "-d",
        "-p",
        "8081:8080",
        "-e",
        "OPENHAB_URL=http://your-openhab-host:8080",
        "-e",
        "OPENHAB_API_TOKEN=your-api-token",
        "--name",
        "openhab-mcp",
        "openhab-mcp"
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

## MCP Tools

The server provides the following tools:

### Item Management
1. `list_items` - List all openHAB items, optionally filtered by tag
2. `get_item` - Get a specific openHAB item by name
3. `create_item` - Create a new openHAB item
4. `update_item` - Update an existing openHAB item
5. `delete_item` - Delete an openHAB item
6. `update_item_state` - Update just the state of an openHAB item

### Thing Management
7. `list_things` - List all openHAB things
8. `get_thing` - Get a specific openHAB thing by UID

### Rule Management
9. `list_rules` - List all openHAB rules, optionally filtered by tag
10. `get_rule` - Get a specific openHAB rule by UID
11. `create_rule` - Create a new openHAB rule
12. `update_rule` - Update an existing openHAB rule with partial updates
13. `update_rule_script_action` - Update a script action in an openHAB rule
14. `delete_rule` - Delete an openHAB rule
15. `run_rule_now` - Run an openHAB rule immediately

### Script Management
16. `list_scripts` - List all openHAB scripts (rules with tag 'Script' and no trigger)
17. `get_script` - Get a specific openHAB script by ID
18. `create_script` - Create a new openHAB script
19. `update_script` - Update an existing openHAB script
20. `delete_script` - Delete an openHAB script

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

For development purposes, please refer to the DEVELOPER.md file for more information on the Docker-based development workflow.

## Notes

This implementation connects to a real openHAB instance via its REST API. For production use, you might want to enhance it with:

1. More comprehensive error handling and logging
2. Additional authentication and security features
3. More sophisticated caching mechanisms
4. Support for more openHAB features (rules, things, etc.)

## License

MIT
