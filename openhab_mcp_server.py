#!/usr/bin/env python3
"""
OpenHAB MCP Server - An MCP server that interacts with a real openHAB instance.

This server uses mcp.server for simplified MCP server implementation and
connects to a real openHAB instance via its REST API.
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from dotenv import load_dotenv

# Configure logging to suppress INFO messages
logging.basicConfig(level=logging.DEBUG)

# Import the MCP server implementation
from mcp.server import FastMCP
from mcp.server.stdio import stdio_server
from mcp.types import JSONRPCError, INVALID_REQUEST

# Import our modules
from models import (
    Item,
    ItemDetails,
    Tag,
    ThingDetails,
    PaginatedThings,
    PaginatedItems,
    PaginatedRules,
    Rule,
    RuleDetails,
    ItemPersistence,
)
from openhab_client import OpenHABClient

from mcp.server.session import ServerSession

####################################################################################
# Temporary monkeypatch which avoids crashing when a POST message is received
# before a connection has been initialized, e.g: after a deployment.
# pylint: disable-next=protected-access
#old__received_request = ServerSession._received_request


#async def _received_request(self, *args, **kwargs):
#    try:
#        return await old__received_request(self, *args, **kwargs)
#    except RuntimeError:
#        pass


# pylint: disable-next=protected-access
#ServerSession._received_request = _received_request
####################################################################################

#mcp = FastMCP("OpenHAB MCP Server")
mcp = FastMCP("OpenHAB MCP Server", stateless_http=True)

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

# @mcp.tool()
# def list_items(filter_tag: Optional[str] = None)-> List[Item]:
#     """List all openHAB items, optionally filtered by tag"""
#     items = openhab_client.list_items(filter_tag)
#     return items


@mcp.tool()
def list_items(
    page: int = 1,
    page_size: int = 15,
    sort_by: str = "name",
    sort_order: str = "asc",
    filter_tag: Optional[str] = None,
    filter_type: Optional[str] = None,
) -> PaginatedItems:
    """
    List openHAB items with basic information with pagination

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 15)
        sort_by: Field to sort by (e.g., "name", "label") (default: "name")
        sort_order: Sort order ("asc" or "desc") (default: "asc")
    """
    return openhab_client.list_items(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        filter_tag=filter_tag,
        filter_type=filter_type,
    )


@mcp.tool()
def get_item_details(item_name: str) -> Optional[ItemDetails]:
    """Get a specific openHAB item with more details including membership for group items by name"""
    item = openhab_client.get_item_details(item_name)
    return item


@mcp.tool()
def create_item(item: ItemDetails) -> ItemDetails:
    """Create a new openHAB item"""
    created_item = openhab_client.create_item(item)
    return created_item


@mcp.tool()
def update_item(item_name: str, item: ItemDetails) -> ItemDetails:
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
def get_item_persistence(
    item_name: str, start: str = None, end: str = None
) -> ItemPersistence:
    """Get the persistence values of an openHAB item between start and end in zulu time format [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']"""
    persistence = openhab_client.get_item_persistence(item_name, start, end)
    return persistence


@mcp.tool()
def list_locations(
    page: int = 1, page_size: int = 15, sort_by: str = "name", sort_order: str = "asc"
) -> PaginatedItems:
    """
    List openHAB locations with basic information with pagination. A location is an item with a tag of 'Location'.

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 15)
        sort_by: Field to sort by (e.g., "name", "label") (default: "name")
        sort_order: Sort order ("asc" or "desc") (default: "asc")
    """
    locations = openhab_client.list_locations(
        page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
    )
    return locations


# @mcp.tool()
# def list_things() -> List[ThingSummary]:
#     """List all openHAB things with summary information"""
#     things = openhab_client.list_things()
#     return things


@mcp.tool()
def list_things(
    page: int = 1, page_size: int = 15, sort_by: str = "UID", sort_order: str = "asc"
) -> PaginatedThings:
    """
    List openHAB things with basic information with pagination

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 15)
        sort_by: Field to sort by (e.g., "UID", "label") (default: "UID")
        sort_order: Sort order ("asc" or "desc") (default: "asc")
    """
    return openhab_client.list_things(
        page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
    )


@mcp.tool()
def get_thing_details(thing_uid: str) -> Optional[ThingDetails]:
    """Get a specific openHAB thing with more details by UID"""
    thing_details = openhab_client.get_thing_details(thing_uid)
    return thing_details


@mcp.tool()
def list_rules(
    page: int = 1,
    page_size: int = 15,
    sort_by: str = "UID",
    sort_order: str = "asc",
    filter_tag: Optional[str] = None,
) -> PaginatedRules:
    """
    List openHAB rules with basic information with pagination

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 15)
        sort_by: Field to sort by (e.g., "UID", "label") (default: "UID")
        sort_order: Sort order ("asc" or "desc") (default: "asc")
        filter_tag: Filter rules by tag (default: None)
    """
    return openhab_client.list_rules(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        filter_tag=filter_tag,
    )


@mcp.tool()
def get_rule_details(rule_uid: str) -> Optional[RuleDetails]:
    """Get a specific openHAB rule with more details by UID"""
    rule_details = openhab_client.get_rule_details(rule_uid)
    return rule_details


@mcp.tool()
def list_scripts(
    page: int = 1, page_size: int = 15, sort_by: str = "UID", sort_order: str = "asc"
) -> PaginatedRules:
    """List all openHAB scripts. A script is a rule without a trigger and tag of 'Script'

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 15)
        sort_by: Field to sort by (e.g., "UID", "label") (default: "UID")
        sort_order: Sort order ("asc" or "desc") (default: "asc")
    """
    return openhab_client.list_scripts(
        page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
    )


@mcp.tool()
def get_script_details(script_id: str) -> Optional[RuleDetails]:
    """Get a specific openHAB script with more details by ID. A script is a rule without a trigger and tag of 'Script'"""
    script_details = openhab_client.get_script_details(script_id)
    return script_details


@mcp.tool()
def update_rule(rule_uid: str, rule_updates: Dict[str, Any]) -> RuleDetails:
    """Update an existing openHAB rule with partial updates"""
    updated_rule = openhab_client.update_rule(rule_uid, rule_updates)
    return updated_rule


@mcp.tool()
def update_rule_script_action(
    rule_uid: str, action_id: str, script_type: str, script_content: str
) -> RuleDetails:
    """Update a script action in an openHAB rule"""
    updated_rule = openhab_client.update_rule_script_action(
        rule_uid, action_id, script_type, script_content
    )
    return updated_rule


@mcp.tool()
def create_rule(rule: Rule) -> RuleDetails:
    """Create a new openHAB rule"""
    created_rule = openhab_client.create_rule(rule)
    return created_rule


@mcp.tool()
def delete_rule(rule_uid: str) -> bool:
    """Delete an openHAB rule"""
    return openhab_client.delete_rule(rule_uid)


@mcp.tool()
def create_script(script_id: str, script_type: str, content: str) -> RuleDetails:
    """Create a new openHAB script. A script is a rule without a trigger and tag of 'Script'"""
    created_script = openhab_client.create_script(script_id, script_type, content)
    return created_script


@mcp.tool()
def update_script(script_id: str, script_type: str, content: str) -> RuleDetails:
    """Update an existing openHAB script. A script is a rule without a trigger and tag of 'Script'"""
    updated_script = openhab_client.update_script(script_id, script_type, content)
    return updated_script


@mcp.tool()
def delete_script(script_id: str) -> bool:
    """Delete an openHAB script. A script is a rule without a trigger and tag of 'Script'"""
    return openhab_client.delete_script(script_id)


@mcp.tool()
def run_rule_now(rule_uid: str) -> bool:
    """Run an openHAB rule immediately"""
    return openhab_client.run_rule_now(rule_uid)


@mcp.tool()
def list_tags(parent_tag_uid: Optional[str] = None) -> List[Tag]:
    """List all openHAB tags, optionally filtered by parent tag"""
    tags = openhab_client.list_tags(parent_tag_uid)
    return tags


@mcp.tool()
def get_tag(tag_uid: str) -> Optional[Tag]:
    """Get a specific openHAB tag by uid"""
    tag = openhab_client.get_tag(tag_uid)
    return tag


@mcp.tool()
def create_tag(tag: Tag) -> Tag:
    """
    Create a new openHAB tag.
    Tags can support multiple levels of hierarchy with the pattern 'parent_child'.
    When adding tags to items only the tag name and not the uid is assigned.
    """
    created_tag = openhab_client.create_tag(tag)
    return created_tag


@mcp.tool()
def delete_tag(tag_uid: str) -> bool:
    """Delete an openHAB tag"""
    return openhab_client.delete_tag(tag_uid)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
