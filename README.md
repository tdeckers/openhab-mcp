# OpenHAB MCP Server

A MCP (Model Context Protocol) server that interacts with a real openHAB instance.

## Overview

This project provides an implementation of an MCP server that connects to a real openHAB instance via its REST API. It allows you to:

- List all openHAB items
- Get specific items by name
- Create new items
- Update existing items
- Delete items
- Update item states

## Requirements

- Python 3.7+
- `uv` package manager
- `modelcontextprotocol` package (for a real implementation)

## Installation

1. Clone this repository
2. Install uv if you don't have it already:

```bash
pip install uv
```

3. Install the dependencies using uv:

```bash
uv pip install -r requirements.txt
```

Alternatively, you can use the installation script which will install dependencies using uv:

```bash
python install_mcp_server.py
```

## Usage

Run the server using Python:

```bash
python openhab_mcp_server.py
```

Or run the server using uv:

```bash
uv run openhab_mcp_server.py
```

This will run the server in an isolated environment managed by uv, ensuring all dependencies are correctly resolved.

## MCP Tools

The server provides the following tools:

1. `list_items` - List all openHAB items, optionally filtered by tag
2. `get_item` - Get a specific openHAB item by name
3. `create_item` - Create a new openHAB item
4. `update_item` - Update an existing openHAB item
5. `delete_item` - Delete an openHAB item
6. `update_item_state` - Update just the state of an openHAB item

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

## Development with uv

uv is a Python package installer and resolver that's designed to be a faster, more reliable alternative to pip. It's also used as a Python environment manager, similar to venv or conda.

### Benefits of using uv

1. **Faster package installation**: uv is significantly faster than pip for installing packages
2. **Improved dependency resolution**: uv provides more reliable dependency resolution
3. **Isolated environments**: uv can create and manage isolated Python environments
4. **Reproducible builds**: uv ensures consistent package installations across different environments

### Using uv for development

To create a new development environment with uv:

```bash
uv venv
```

To activate the environment:

```bash
source .venv/bin/activate  # On Linux/macOS
.venv\Scripts\activate     # On Windows
```

To install packages in development mode:

```bash
uv pip install -e .
```

## Notes

This implementation connects to a real openHAB instance via its REST API. For production use, you might want to enhance it with:

1. More comprehensive error handling and logging
2. Additional authentication and security features
3. More sophisticated caching mechanisms
4. Support for more openHAB features (rules, things, etc.)

## License

MIT
