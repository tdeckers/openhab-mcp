# OpenHAB MCP Server

A Model Context Protocol (MCP) server that provides AI assistants with comprehensive access to an openHAB smart home system.

## Overview

This project implements an MCP server that connects to an openHAB instance via its REST API, enabling AI assistants to interact with and manage your smart home system using natural language.

### Key Features

#### Items Management
- List, view, create, update, and delete items
- Get and update item states
- Manage item metadata and tags
- Handle item persistence data
- Support for group items and members

#### Things Management
- List all things with pagination
- View detailed information about specific things
- Manage thing channels and links
- Handle inbox items (approve, ignore, delete)

#### Rules & Scripts
- Full CRUD operations for rules
- Update rule script actions
- Run rules on demand
- Enable/disable rules
- Script management (specialized rules with no triggers)

#### Semantic Model
- Manage semantic tags and categories
- Assign semantic and non-semantic tags to items
- Hierarchical tag structure support

## Requirements

- Python 3.9+
- Docker (for containerized deployment)
- OpenHAB 3.4+ instance

## Quick Start with Docker Compose

The easiest way to get started is using the provided Docker Compose configuration:

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/openhab-mcp.git
   cd openhab-mcp
   ```

2. Copy the example environment file to the docker directory and update it with your configuration:
   ```bash
   cp docker/.env.example docker/.env
   # Edit docker/.env with your settings
   ```

3. Start the service:
   ```bash
   docker-compose -f docker/docker-compose.yml up -d
   ```

## Manual Installation

### Prerequisites
- Python 3.9+
- pip
- virtualenv (recommended)

### Installation Steps

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

3. Configure environment variables (see Configuration section below)

4. Run the server:
   ```bash
   python -m openhab_mcp.openhab_mcp_server
   ```

## Configuration

The server can be configured using environment variables or a `.env` file in the `docker` directory.

### Required Variables
- `OPENHAB_URL`: URL of your openHAB instance (e.g., `http://openhab:8080`)

### Authentication (choose one method)
- `OPENHAB_API_TOKEN`: API token for authentication (recommended)
- `OPENHAB_USERNAME` and `OPENHAB_PASSWORD`: Basic auth credentials

### Server Configuration
- `MCP_HOST`: Host to bind the server to (default: `0.0.0.0`)
- `MCP_PORT`: Port to run the server on (default: `8000`)
- `LOG_LEVEL`: Logging level (default: `INFO`)
- `OPENHAB_MCP_TRANSPORT`: Transport mode (`stdio`, `streamable-http`, or `sse`) (default: `stdio`)

## Integration with AI Assistants

The OpenHAB MCP Server can be used with various AI assistants that support the MCP protocol, including Claude and Cline.

### Prerequisites

- For Claude: [Claude Desktop app](https://claude.ai/desktop) or compatible client
- For Cline: [Cline VSCode extension](https://marketplace.visualstudio.com/items?itemName=Anthropic.cline)

### Configuration

#### Docker Compose (Recommended)

1. Update the `docker-compose.yml` with your configuration
2. Start the service:
   ```bash
   docker-compose -f docker/docker-compose.yml up -d
   ```

#### Manual Configuration

For manual configuration with Claude Desktop, create a configuration file at:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

Example configuration:

```json
{
  "mcp_servers": [
    {
      "name": "openhab-mcp",
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-p", "8000:8000",
        "-e", "OPENHAB_URL=http://openhab:8080",
        "-e", "OPENHAB_API_TOKEN=your-api-token",
        "-e", "MCP_HOST=0.0.0.0",
        "-e", "MCP_PORT=8000",
        "-e", "LOG_LEVEL=INFO",
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

## Available Tools

The MCP server provides a comprehensive set of tools for managing your openHAB system. Here's a categorized list of available tools:

### Items Management
- `list_items` - List items with pagination and filtering
- `get_item` - Get detailed information about a specific item
- `create_item` - Create a new item
- `update_item` - Update an existing item
- `delete_item` - Remove an item
- `get_item_state` - Get current state of an item
- `update_item_state` - Update item state
- `send_command` - Send a command to an item
- `get_item_persistence` - Retrieve historical state data
- `update_item_members` - Update group item members in bulk

### Item Metadata & Tags
- `get_item_metadata_namespaces` - List metadata namespaces
- `get_item_metadata` - Get metadata for an item
- `add_or_update_item_metadata` - Manage item metadata
- `remove_item_metadata` - Remove metadata
- `list_semantic_tags` - Browse semantic tags
- `get_semantic_tag` - Get tag details
- `create_semantic_tag` - Create new semantic tags
- `delete_semantic_tag` - Remove semantic tags
- `add_item_semantic_tag` - Tag items semantically
- `remove_item_semantic_tag` - Remove semantic tags
- `add_item_non_semantic_tag` - Add regular tags
- `remove_item_non_semantic_tag` - Remove regular tags

### Things & Links
- `list_things` - Browse things with pagination
- `get_thing` - Get thing details
- `create_thing` - Add new things
- `update_thing` - Modify existing things
- `delete_thing` - Remove things
- `get_thing_channels` - List thing channels
- `list_links` - View item-thing links
- `get_link` - Get link details
- `create_or_update_link` - Manage links
- `delete_link` - Remove links

### Rules & Scripts
- `list_rules` - Browse rules
- `get_rule` - Get rule details
- `create_rule` - Create new rules
- `update_rule` - Modify rules
- `delete_rule` - Remove rules
- `update_rule_script_action` - Update rule scripts
- `run_rule_now` - Execute rules immediately
- `set_rule_enabled` - Toggle rule state
- `list_scripts` - List available scripts
- `get_script` - Get script details
- `create_script` - Create new scripts
- `update_script` - Modify scripts
- `delete_script` - Remove scripts

### Inbox & Discovery
- `list_inbox_things` - View discovered devices
- `approve_inbox_thing` - Approve new devices
- `ignore_inbox_thing` - Ignore devices
- `unignore_inbox_thing` - Reconsider ignored devices
- `delete_inbox_thing` - Remove from inbox

### Task Automation
- `list_task_templates` - Find automation templates
- `get_task_template` - Get template details
- `save_task_template_override` - Customize templates
- `delete_task_template_override` - Remove custom templates
- `get_task_template_schema` - View template structure

## Development

### Running Tests

```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Run tests
pytest tests/
```

### Building the Docker Image

```bash
docker build -t openhab-mcp .
```

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
