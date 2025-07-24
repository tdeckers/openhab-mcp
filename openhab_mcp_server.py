#!/usr/bin/env python3
"""
OpenHAB MCP Server - An MCP server that interacts with a real openHAB instance.

This server uses mcp.server for simplified MCP server implementation and
connects to a real openHAB instance via its REST API.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Configure logging to suppress INFO messages
logging.basicConfig(level=logging.WARNING)

# Import the MCP server implementation
from mcp.server import FastMCP
from mcp.server.stdio import stdio_server
from mcp.types import INVALID_REQUEST, JSONRPCError

# Import our modules
from models import Item, Rule, Thing
from openhab_client import OpenHABClient

mcp = FastMCP("OpenHAB MCP Server")

# Load environment variables from .env file
env_file = Path(".env")
if env_file.exists():
    print(f"Loading environment variables from {env_file}", file=sys.stderr)
    load_dotenv(env_file, verbose=True)

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
def list_items(filter_tag: Optional[str] = None) -> List[Item]:
    """List all openHAB items, optionally filtered by tag"""
    items = openhab_client.list_items(filter_tag)
    return items


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
def list_things() -> List[Thing]:
    """List all openHAB things"""
    things = openhab_client.list_things()
    return things


@mcp.tool()
def get_thing(thing_uid: str) -> Optional[Thing]:
    """Get a specific openHAB thing by UID"""
    thing = openhab_client.get_thing(thing_uid)
    return thing


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


def main():
    """Main entry point for the OpenHAB MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
