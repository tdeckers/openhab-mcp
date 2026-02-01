#!/usr/bin/env python3
"""
OpenHAB MCP Server - An MCP server that interacts with a real openHAB instance.

This server uses mcp.server for simplified MCP server implementation and
connects to a real openHAB instance via its REST API.
"""

import contextlib
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from dotenv import load_dotenv

# Import the MCP server implementation
from mcp.server import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount

# Import our modules
from models import (
    ConfigStatusMessage,
    EnrichedItemChannelLinkDTO,
    FirmwareDTO,
    FirmwareStatusDTO,
    Item,
    ItemChannelLinkDTO,
    Rule,
    Thing,
    ThingDTO,
    ThingStatusInfo,
)
from openhab_client import OpenHABClient

# Configure logging to suppress INFO messages
logging.basicConfig(level=logging.WARNING)

# Load environment variables from .env file
env_file = Path(".env")
if env_file.exists():
    print(f"Loading environment variables from {env_file}", file=sys.stderr)
    load_dotenv(env_file, verbose=True)

MCP_MODE_ENV = os.environ.get("MCP_MODE")
MCP_TRANSPORT_ENV = os.environ.get("MCP_TRANSPORT")

if MCP_MODE_ENV is None:
    MCP_MODE = "stdio"
else:
    MCP_MODE = MCP_MODE_ENV.strip().lower()
    if MCP_MODE not in ("stdio", "remote"):
        logging.warning(
            "Invalid MCP_MODE value '%s'. Expected 'stdio' or 'remote'. "
            "Falling back to 'stdio'.",
            MCP_MODE_ENV,
        )
        MCP_MODE = "stdio"

if MCP_TRANSPORT_ENV is not None and MCP_MODE_ENV is None:
    transport = MCP_TRANSPORT_ENV.strip().lower()
    if transport in ("http", "streamable-http", "streamable_http", "sse"):
        MCP_MODE = "remote"
        logging.warning(
            "MCP_TRANSPORT is deprecated. Use MCP_MODE=remote instead.",
        )
    else:
        logging.warning(
            "Invalid MCP_TRANSPORT value '%s'. Use MCP_MODE instead.",
            MCP_TRANSPORT_ENV,
        )
elif MCP_TRANSPORT_ENV is not None and MCP_MODE_ENV is not None:
    logging.warning(
        "MCP_TRANSPORT is deprecated and ignored when MCP_MODE is set.",
    )

if MCP_MODE == "remote":
    mcp = FastMCP("OpenHAB MCP Server", host="0.0.0.0")
else:
    mcp = FastMCP("OpenHAB MCP Server")

# Get OpenHAB connection settings from environment variables
OPENHAB_URL = os.environ.get("OPENHAB_URL", "http://localhost:8080")
OPENHAB_API_TOKEN = os.environ.get("OPENHAB_API_TOKEN")
OPENHAB_USERNAME = os.environ.get("OPENHAB_USERNAME")
OPENHAB_PASSWORD = os.environ.get("OPENHAB_PASSWORD")

if not OPENHAB_API_TOKEN and not (OPENHAB_USERNAME and OPENHAB_PASSWORD):
    print(
        "Warning: No authentication credentials found in environment variables.",
        file=sys.stderr,
    )
    print(
        "Set OPENHAB_API_TOKEN or OPENHAB_USERNAME/OPENHAB_PASSWORD in .env file.",
        file=sys.stderr,
    )

# Initialize the real OpenHAB client
openhab_client = OpenHABClient(
    base_url=OPENHAB_URL,
    api_token=OPENHAB_API_TOKEN,
    username=OPENHAB_USERNAME,
    password=OPENHAB_PASSWORD,
)


@mcp.tool()
def list_items(
    page: int = 1,
    page_size: int = 15,
    sort_order: str = "asc",
    filter_tag: Optional[str] = None,
    filter_type: Optional[str] = None,
    filter_name: Optional[str] = None,
    filter_label: Optional[str] = None,
) -> Dict[str, Any]:
    """List openHAB items with pagination and optional filtering."""
    items = openhab_client.list_items(
        page=page,
        page_size=page_size,
        sort_order=sort_order,
        filter_tag=filter_tag,
        filter_type=filter_type,
        filter_name=filter_name,
        filter_label=filter_label,
    )
    return items.dict()


@mcp.tool()
def get_item(item_name: str) -> Optional[Item]:
    """Get a specific openHAB item by name"""
    item = openhab_client.get_item(item_name)
    return item


@mcp.tool()
def create_item(item: Item) -> Item:
    """Create a new openHAB item"""
    created_item = openhab_client.create_item(item)
    return created_item


@mcp.tool()
def update_item(item_name: str, item: Item) -> Item:
    """Update an existing openHAB item"""
    updated_item = openhab_client.update_item(item_name, item)
    return updated_item


@mcp.tool()
def delete_item(item_name: str) -> bool:
    """Delete an openHAB item"""
    return openhab_client.delete_item(item_name)


@mcp.tool()
def update_item_state(item_name: str, state: str) -> Item:
    """Update the state of an openHAB item"""
    updated_item = openhab_client.update_item_state(item_name, state)
    return updated_item


@mcp.tool()
def list_things(
    page: int = 1,
    page_size: int = 50,
    sort_order: str = "asc",
    filter_uid: Optional[str] = None,
    filter_label: Optional[str] = None,
) -> Dict[str, Any]:
    """List openHAB things with pagination and optional filtering."""
    things = openhab_client.list_things(
        page=page,
        page_size=page_size,
        sort_order=sort_order,
        filter_uid=filter_uid,
        filter_label=filter_label,
    )
    return things.dict()


@mcp.tool()
def get_thing(thing_uid: str) -> Optional[Thing]:
    """Get a specific openHAB thing by UID"""
    thing = openhab_client.get_thing(thing_uid)
    return thing


@mcp.tool()
def create_thing(thing: ThingDTO) -> Thing:
    """Create a new openHAB thing"""
    created_thing = openhab_client.create_thing(thing)
    return created_thing


@mcp.tool()
def update_thing(thing_uid: str, thing: ThingDTO) -> Thing:
    """Update an existing openHAB thing"""
    updated_thing = openhab_client.update_thing(thing_uid, thing)
    return updated_thing


@mcp.tool()
def delete_thing(thing_uid: str, force: bool = False) -> bool:
    """Delete an openHAB thing"""
    return openhab_client.delete_thing(thing_uid, force)


@mcp.tool()
def update_thing_config(thing_uid: str, configuration: Dict[str, Any]) -> Thing:
    """Update an openHAB thing's configuration"""
    updated_thing = openhab_client.update_thing_config(thing_uid, configuration)
    return updated_thing


@mcp.tool()
def get_thing_config_status(thing_uid: str) -> List[ConfigStatusMessage]:
    """Get openHAB thing configuration status"""
    config_status = openhab_client.get_thing_config_status(thing_uid)
    return config_status


@mcp.tool()
def set_thing_enabled(thing_uid: str, enabled: bool) -> Thing:
    """Set the enabled status of an openHAB thing"""
    updated_thing = openhab_client.set_thing_enabled(thing_uid, enabled)
    return updated_thing


@mcp.tool()
def get_thing_status(thing_uid: str) -> ThingStatusInfo:
    """Get openHAB thing status"""
    thing_status = openhab_client.get_thing_status(thing_uid)
    return thing_status


@mcp.tool()
def get_thing_firmware_status(thing_uid: str) -> Optional[FirmwareStatusDTO]:
    """Get openHAB thing firmware status"""
    firmware_status = openhab_client.get_thing_firmware_status(thing_uid)
    return firmware_status


@mcp.tool()
def get_available_firmwares(thing_uid: str) -> List[FirmwareDTO]:
    """Get available firmwares for an openHAB thing"""
    firmwares = openhab_client.get_available_firmwares(thing_uid)
    return firmwares


@mcp.tool()
def list_rules(filter_tag: Optional[str] = None) -> List[Rule]:
    """List all openHAB rules, optionally filtered by tag"""
    rules = openhab_client.list_rules(filter_tag)
    return rules


@mcp.tool()
def get_rule(rule_uid: str) -> Optional[Rule]:
    """Get a specific openHAB rule by UID"""
    rule = openhab_client.get_rule(rule_uid)
    return rule


@mcp.tool()
def list_scripts() -> List[Rule]:
    """
    List all openHAB scripts. A script is a rule without a trigger and tag of 'Script'
    """
    scripts = openhab_client.list_scripts()
    return scripts


@mcp.tool()
def get_script(script_id: str) -> Optional[Rule]:
    """
    Get a specific openHAB script by ID. A script is a rule without a trigger and
    tag of 'Script'
    """
    script = openhab_client.get_script(script_id)
    return script


@mcp.tool()
def update_rule(rule_uid: str, rule_updates: Dict[str, Any]) -> Rule:
    """Update an existing openHAB rule with partial updates"""
    updated_rule = openhab_client.update_rule(rule_uid, rule_updates)
    return updated_rule


@mcp.tool()
def update_rule_script_action(
    rule_uid: str, action_id: str, script_type: str, script_content: str
) -> Rule:
    """Update a script action in an openHAB rule"""
    updated_rule = openhab_client.update_rule_script_action(
        rule_uid, action_id, script_type, script_content
    )
    return updated_rule


@mcp.tool()
def create_rule(rule: Rule) -> Rule:
    """Create a new openHAB rule"""
    created_rule = openhab_client.create_rule(rule)
    return created_rule


@mcp.tool()
def delete_rule(rule_uid: str) -> bool:
    """Delete an openHAB rule"""
    return openhab_client.delete_rule(rule_uid)


@mcp.tool()
def create_script(script_id: str, script_type: str, content: str) -> Rule:
    """
    Create a new openHAB script. A script is a rule without a trigger and
    tag of 'Script'
    """
    created_script = openhab_client.create_script(script_id, script_type, content)
    return created_script


@mcp.tool()
def update_script(script_id: str, script_type: str, content: str) -> Rule:
    """
    Update an existing openHAB script. A script is a rule without a trigger and
    tag of 'Script'
    """
    updated_script = openhab_client.update_script(script_id, script_type, content)
    return updated_script


@mcp.tool()
def delete_script(script_id: str) -> bool:
    """
    Delete an openHAB script. A script is a rule without a trigger and tag of
    'Script'
    """
    return openhab_client.delete_script(script_id)


@mcp.tool()
def run_rule_now(rule_uid: str) -> bool:
    """Run an openHAB rule immediately"""
    return openhab_client.run_rule_now(rule_uid)


@mcp.tool()
def list_links(
    channel_uid: Optional[str] = None, item_name: Optional[str] = None
) -> List[EnrichedItemChannelLinkDTO]:
    """
    List all openHAB item-channel links, optionally filtered by channel UID
    or item name.
    """
    links = openhab_client.list_links(channel_uid, item_name)
    return links


@mcp.tool()
def get_link(item_name: str, channel_uid: str) -> Optional[EnrichedItemChannelLinkDTO]:
    """Get a specific openHAB item-channel link"""
    link = openhab_client.get_link(item_name, channel_uid)
    return link


@mcp.tool()
def create_or_update_link(
    item_name: str, channel_uid: str, link_data: Optional[ItemChannelLinkDTO] = None
) -> bool:
    """Create or update an openHAB item-channel link"""
    return openhab_client.create_or_update_link(item_name, channel_uid, link_data)


@mcp.tool()
def delete_link(item_name: str, channel_uid: str) -> bool:
    """Delete a specific openHAB item-channel link"""
    return openhab_client.delete_link(item_name, channel_uid)


@mcp.tool()
def get_orphan_links() -> List[EnrichedItemChannelLinkDTO]:
    """Get orphaned openHAB item-channel links (links to non-existent channels)"""
    orphan_links = openhab_client.get_orphan_links()
    return orphan_links


@mcp.tool()
def purge_orphan_links() -> bool:
    """Remove all orphaned openHAB item-channel links"""
    return openhab_client.purge_orphan_links()


@mcp.tool()
def delete_all_links_for_object(object_name: str) -> bool:
    """Delete all openHAB links for a specific item or thing"""
    return openhab_client.delete_all_links_for_object(object_name)


def _build_remote_app() -> Starlette:
    mcp.settings.streamable_http_path = "/"
    mcp.settings.sse_path = "/"

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        async with mcp.session_manager.run():
            yield

    return Starlette(
        routes=[
            Mount("/mcp", app=mcp.streamable_http_app()),
            Mount("/sse", app=mcp.sse_app()),
        ],
        lifespan=lifespan,
    )


def main():
    """Main entry point for the OpenHAB MCP server."""
    if MCP_MODE == "remote":
        app = _build_remote_app()
        uvicorn.run(app, host=mcp.settings.host, port=mcp.settings.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
