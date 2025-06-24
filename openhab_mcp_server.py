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
from pydantic import Field

# Configure logging to suppress INFO messages
logging.basicConfig(level=logging.INFO)

# Import the MCP server implementation
from mcp.server import FastMCP
from mcp.types import TextContent

from template_manager import TemplateManager, ProcessTemplate

template_manager = TemplateManager()

# Import our modules
from models import (
    ItemCreate,
    ItemUpdate,
    ItemMetadata,
    Link,
    Tag,
    ThingCreate,
    ThingUpdate,
    RuleCreate,
    RuleUpdate,
)
from openhab_client import OpenHABClient

mcp = FastMCP(name="OpenHAB MCP Server")

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
OPENHAB_MCP_TRANSPORT = os.environ.get("OPENHAB_MCP_TRANSPORT", "stdio")

if OPENHAB_MCP_TRANSPORT == "streamable-http":
    mcp = FastMCP("OpenHAB MCP Server", stateless_http=True)
else:
    mcp = FastMCP("OpenHAB MCP Server")

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


# Item Tools
@mcp.tool()
def list_items(
    page: int = Field(
        1,
        description="Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true",
    ),
    page_size: int = Field(15, description="Number of elements shown per page"),
    sort_order: str = Field("asc", description="Sort order", examples=["asc", "desc"]),
    filter_tag: str = Field(
        "",
        description="Optional filter items by tag (either a non-semantic tag or the name of a semantic tag). All available semantic tags can be retrieved from the `list_tags` tool",
        examples=["Location", "Window", "Light", "FrontDoor"],
    ),
    filter_type: str = Field(
        "",
        description="Optional filter items by type",
        examples=["Switch", "Group", "String", "DateTime"],
    ),
    filter_name: str = Field(
        "",
        description="Optional filter items by name. All items that contain the filter value in their name are returned",
        examples=["Kitchen", "LivingRoom", "Bedroom"],
    ),
    filter_fields: List[str] = Field(
        [],
        description="Optional filter items by fields. Item name will always be included by default.",
        examples=["name", "label", "type", "semantic_tags", "non_semantic_tags"],
    ),
) -> Dict[str, Any]:
    """
    Gives a list of openHAB items with only basic information. Use this tool
    to get an overview of your items. Use the `get_item_details` tool to get
    more information about a specific item.

    Args:
        page: Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true
        page_size: Number of elements shown per page
        sort_order: Sort order
        filter_tag: Optional filter items by tag (either a non-semantic tag or the name of a semantic tag). All available semantic tags can be retrieved from the `list_tags` tool
        filter_type: Optional filter items by type
        filter_name: Optional filter items by name. All items that contain the filter value in their name are returned
        filter_fields: Optional filter items by fields. Item name will always be included by default.
    """
    return openhab_client.list_items(
        page=page,
        page_size=page_size,
        sort_order=sort_order,
        filter_tag=filter_tag,
        filter_type=filter_type,
        filter_name=filter_name,
        filter_fields=filter_fields,
    )


@mcp.tool()
def get_item(
    item_name: str = Field(..., description="Name of the item to get details for"),
) -> Dict[str, Any]:
    """
    Gives a detailed description of an openHAB item. Use this tool to get
    information about a specific item.

    Args:
        item_name: Name of the item to get details for
    """
    return openhab_client.get_item(item_name)


@mcp.tool()
def get_create_item_schema() -> Dict[str, Any]:
    """
    Get the JSON schema for creating an item.
    """
    return ItemCreate.model_json_schema()


@mcp.tool()
def create_item(
    item: ItemCreate = Field(..., description="Item details to create"),
) -> Dict[str, Any]:
    """
    Create a new openHAB item

    Args:
        item: Item details to create
    """
    return openhab_client.create_item(item)


@mcp.tool()
def update_item(
    item: ItemUpdate = Field(..., description="Item details to update"),
) -> Dict[str, Any]:
    """
    Update an existing openHAB item

    Args:
        item: Item details to update
    """
    return openhab_client.update_item(item)


@mcp.tool()
def delete_item(
    item_name: str = Field(..., description="Name of the item to delete"),
) -> bool:
    """
    Delete an openHAB item

    Args:
        item_name: Name of the item to delete
    """
    return openhab_client.delete_item(item_name)


@mcp.tool()
def get_item_state(
    item_name: str = Field(..., description="Name of the item to get state for"),
) -> str:
    """
    Get the state of an openHAB item

    Args:
        item_name: Name of the item to get state for
    """
    return openhab_client.get_item_state(item_name)


@mcp.tool()
def update_item_state(
    item_name: str = Field(..., description="Name of the item to update state for"),
    state: str = Field(
        ...,
        description="State to update the item to as string. Type conversion must be possible for the item type",
        examples=[
            "ON",
            "OFF",
            "140.5",
            "14%",
            "20 kWH",
            "2025-06-03T22:21:13.123Z",
            "This is a text",
        ],
    ),
) -> Dict[str, Any]:
    """
    Update the state of an openHAB item

    Args:
        item_name: Name of the item to update state for
        state: State to update the item to. Allowed states depend on the item type
    """
    return openhab_client.update_item_state(item_name, state)


@mcp.tool()
def send_command(
    item_name: str = Field(..., description="Name of the item to send command to"),
    command: str = Field(
        ...,
        description="Command to send to the item. Allowed commands depend on the item type",
        examples=[
            "ON",
            "OFF",
            "140.5",
            "14%",
            "20 kWH",
            "2025-06-03T22:21:13.123Z",
            "This is a text",
        ],
    ),
) -> Dict[str, Any]:
    """
    Send a command to an openHAB item

    Args:
        item_name: Name of the item to send command to
        command: Command to send to the item. Allowed commands depend on the item type
    """
    return openhab_client.send_command(item_name, command)


@mcp.tool()
def get_item_persistence(
    item_name: str = Field(..., description="Name of the item to get persistence for"),
    start: str = Field(
        ...,
        description="Start time in UTC/Zulu time format [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']",
        examples=["2025-06-03T22:21:13.123Z"],
    ),
    end: str = Field(
        ...,
        description="End time in UTC/Zulu time format [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']",
        examples=["2025-06-03T22:21:13.123Z"],
    ),
) -> Dict[str, Any]:
    """
    Get the persistence values of an openHAB item between start and end in UTC/Zulu time format
    [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']

    Args:
        item_name: Name of the item to get persistence for
        start: Start time in UTC/Zulu time format [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']
        end: End time in UTC/Zulu time format [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']
    """
    return openhab_client.get_item_persistence(item_name, start, end)


# Item Metadata Tools
@mcp.tool()
def get_item_metadata_namespaces(
    item_name: str = Field(
        ..., description="Name of the item to get metadata namespaces for"
    ),
) -> List[str]:
    """
    Get the namespaces of metadata for a specific openHAB item.

    Args:
        item_name: Name of the item to get metadata namespaces for

    Returns:
        List[str]: A list of metadata namespaces

    Raises:
        ValueError: If no item name is provided or item with the given name does not exist
    """
    return openhab_client.get_item_metadata_namespaces(item_name)


@mcp.tool()
def get_item_metadata(
    item_name: str = Field(..., description="Name of the item to get metadata for"),
    namespace: str = Field(..., description="Namespace of the metadata"),
) -> Dict[str, Any]:
    """
    Get the metadata for a specific openHAB item.

    Args:
        item_name: Name of the item to get metadata for
        namespace: Namespace of the metadata

    Returns:
        Dict[str, Any]: The metadata for the item

    Raises:
        ValueError: If no item name is provided or item with the given name does not exist
    """
    return openhab_client.get_item_metadata(item_name, namespace)


@mcp.tool()
def get_item_metadata_schema() -> Dict[str, Any]:
    """
    Get the JSON schema for creating item metadata.
    """
    return ItemMetadata.model_json_schema()


@mcp.tool()
def add_or_update_item_metadata(
    item_name: str = Field(
        ..., description="Name of the item to add or update metadata for"
    ),
    namespace: str = Field(..., description="Namespace of the metadata"),
    metadata: ItemMetadata = Field(..., description="Metadata to add or update"),
) -> Dict[str, Any]:
    """
    Add or update metadata for a specific openHAB item

    Args:
        item_name: Name of the item to add or update metadata for
        namespace: Namespace of the metadata
        metadata: Metadata to add or update
    """
    return openhab_client.add_or_update_item_metadata(item_name, namespace, metadata)


@mcp.tool()
def remove_item_metadata(
    item_name: str = Field(..., description="Name of the item to remove metadata for"),
    namespace: str = Field(..., description="Namespace of the metadata"),
) -> bool:
    """
    Remove metadata for a specific openHAB item

    Args:
        item_name: Name of the item to remove metadata for
        namespace: Namespace of the metadata
    """
    return openhab_client.remove_item_metadata(item_name, namespace)


# Item member tools
@mcp.tool()
def add_item_member(
    item_name: str = Field(..., description="Name of the item to add member for"),
    member_item_name: str = Field(..., description="Name of the member item to add"),
) -> Dict[str, Any]:
    """
    Add a member to an item (group).

    Args:
        item_name: Name of the parent item (group)
        member_item_name: Name of the member item to add

    Returns:
        The complete updated item

    Raises:
        ValueError: If the item with the given name does not exist or is not a group item
        ValueError: If the member item with the given name does not exist or is not editable
    """
    return openhab_client.add_item_member(item_name, member_item_name)


@mcp.tool()
def remove_item_member(
    item_name: str = Field(..., description="Name of the item to remove member for"),
    member_item_name: str = Field(..., description="Name of the member item to remove"),
) -> Dict[str, Any]:
    """
    Remove a member from an item (group).

    Args:
        item_name: Name of the parent item (group)
        member_item_name: Name of the member item to remove

    Returns:
        The complete updated item

    Raises:
        ValueError: If the item with the given name does not exist or is not a group item
        ValueError: If the member item with the given name does not exist or is not editable
    """
    return openhab_client.remove_item_member(item_name, member_item_name)


# Links
@mcp.tool()
def list_links(
    page: int = Field(
        1,
        description="Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true",
    ),
    page_size: int = Field(15, description="Number of elements per page"),
    sort_order: str = Field("asc", description="Sort order", examples=["asc", "desc"]),
    item_name: Optional[str] = Field(
        None, description="Optional filter links by item name"
    ),
) -> Dict[str, Any]:
    """
    List all openHAB item to thing links, optionally filtered by item name with pagination.

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 50)
        sort_order: Sort order ("asc" or "desc") (default: "asc")
        item_name: Optional filter links by item name (default: None)
    """
    return openhab_client.list_links(page, page_size, sort_order, item_name)


@mcp.tool()
def get_link(
    item_name: str = Field(..., description="Name of the item to get link for"),
    channel_uid: str = Field(..., description="UID of the channel to get link for"),
) -> Optional[Dict[str, Any]]:
    """
    Get a specific openHAB item to thing link by item name and channel UID.

    Args:
        item_name: Name of the item to get link for
        channel_uid: UID of the channel to get link for
    """
    return openhab_client.get_link(item_name, channel_uid)

@mcp.tool()
def get_create_or_update_link_schema() -> Dict[str, Any]:
    """
    Get the JSON schema for creating a link.
    """
    return Link.model_json_schema()

@mcp.tool()
def create_or_update_link(
    link: Link = Field(..., description="Link to create or update")
) -> Dict[str, Any]:
    """
    Create a new openHAB item to thing link or update an existing one.

    Args:
        link: Link to create or update
    """
    return openhab_client.create_or_update_link(link)


@mcp.tool()
def delete_link(
    item_name: str = Field(..., description="Name of the item to delete link for"),
    channel_uid: str = Field(..., description="UID of the channel to delete link for"),
) -> bool:
    """
    Delete an openHAB item to thing link.

    Args:
        item_name: Name of the item to delete link for
        channel_uid: UID of the channel to delete link for
    """
    return openhab_client.delete_link(item_name, channel_uid)


# Thing Tools
@mcp.tool()
def list_things(
    page: int = Field(
        1,
        description="Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true",
    ),
    page_size: int = Field(15, description="Number of elements per page"),
    sort_order: str = Field("asc", description="Sort order", examples=["asc", "desc"]),
) -> Dict[str, Any]:
    """
    List openHAB things with basic information with pagination. Use the `get_thing_details` tool to get
    more information about a specific thing.

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 50)
        sort_order: Sort order ("asc" or "desc") (default: "asc")
    """
    return openhab_client.list_things(
        page=page, page_size=page_size, sort_order=sort_order
    )


@mcp.tool()
def get_thing(
    thing_uid: str = Field(..., description="UID of the thing to get details for"),
) -> Dict[str, Any]:
    """
    Get the details of a specific openHAB thing by UID.

    Args:
        thing_uid: UID of the thing to get details for
    """
    return openhab_client.get_thing(thing_uid)


@mcp.tool()
def get_create_thing_schema() -> Dict[str, Any]:
    """
    Get the JSON schema for creating a thing.
    """
    return ThingCreate.model_json_schema()


@mcp.tool()
def get_update_thing_schema() -> Dict[str, Any]:
    """
    Get the JSON schema for updating a thing.
    """
    return ThingUpdate.model_json_schema()


@mcp.tool()
def create_thing(
    thing: ThingCreate = Field(..., description="Thing to create"),
) -> Dict[str, Any]:
    """
    Create a new openHAB thing.

    Args:
        thing: Thing to create
    """
    return openhab_client.create_thing(thing)


@mcp.tool()
def update_thing(
    thing: ThingUpdate = Field(..., description="Thing to update"),
) -> Dict[str, Any]:
    """
    Update an existing openHAB thing.

    Args:
        thing: Thing to update
    """
    return openhab_client.update_thing(thing)


@mcp.tool()
def delete_thing(
    thing_uid: str = Field(..., description="UID of the thing to delete"),
) -> bool:
    """
    Delete an openHAB thing.

    Args:
        thing_uid: UID of the thing to delete
    """
    return openhab_client.delete_thing(thing_uid)


@mcp.tool()
def get_thing_channels(
    thing_uid: str = Field(..., description="UID of the thing to get details for"),
    linked_only: bool = Field(
        False, description="If True, only return channels with linked items"
    ),
) -> Dict[str, Any]:
    """
    Get the channels of a specific openHAB thing by UID.

    Args:
        thing_uid: UID of the thing to get details for
        linked_only: If True, only return channels with linked items
    """
    try:
        return openhab_client.get_thing_channels(thing_uid, linked_only)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


# Rule Tools
@mcp.tool()
def list_rules(
    page: int = Field(
        1,
        description="Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true",
    ),
    page_size: int = Field(15, description="Number of elements per page"),
    sort_order: str = Field("asc", description="Sort order", examples=["asc", "desc"]),
    filter_tag: Optional[str] = Field(
        None, description="Filter rules by tag (default: None)"
    ),
) -> Dict[str, Any]:
    """
    List openHAB rules with basic information with pagination

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 15)
        sort_order: Sort order ("asc" or "desc") (default: "asc")
        filter_tag: Filter rules by tag (default: None)
    """
    return openhab_client.list_rules(
        page=page,
        page_size=page_size,
        sort_order=sort_order,
        filter_tag=filter_tag,
    )


@mcp.tool()
def get_rule(
    rule_uid: str = Field(..., description="UID of the rule to get details for"),
) -> Dict[str, Any]:
    """
    Get a specific openHAB rule with more details by UID.

    Args:
        rule_uid: UID of the rule to get details for
    """
    return openhab_client.get_rule(rule_uid)


@mcp.tool()
def get_create_rule_schema() -> dict:
    """
    Get the JSON schema for creating a rule.
    """
    return RuleCreate.model_json_schema()


@mcp.tool()
def get_update_rule_schema() -> dict:
    """
    Get the JSON schema for updating a rule.
    """
    return RuleUpdate.model_json_schema()


@mcp.tool()
def create_rule(
    rule: RuleCreate = Field(..., description="Rule to create")
) -> Dict[str, Any]:
    """
    Create a new openHAB rule.

    Args:
        rule: Rule to create
    """
    rule.raise_for_errors()
    return openhab_client.create_rule(rule)


@mcp.tool()
def update_rule(
    rule_uid: str = Field(..., description="UID of the rule to update"),
    rule_updates: RuleUpdate = Field(
        ..., description="Partial updates to apply to the rule"
    ),
) -> Dict[str, Any]:
    """
    Update an existing openHAB rule with partial updates.

    Args:
        rule_uid: UID of the rule to update
        rule_updates: Partial updates to apply to the rule
    """
    return openhab_client.update_rule(rule_uid, rule_updates)


@mcp.tool()
def update_rule_script_action(
    rule_uid: str = Field(..., description="UID of the rule to update"),
    action_id: str = Field(..., description="ID of the action to update"),
    script_type: str = Field(..., description="Type of the script"),
    script_content: str = Field(..., description="Content of the script"),
) -> Dict[str, Any]:
    """
    Update a script action in an openHAB rule.

    Args:
        rule_uid: UID of the rule to update
        action_id: ID of the action to update
        script_type: Type of the script
        script_content: Content of the script
    """
    return openhab_client.update_rule_script_action(
        rule_uid, action_id, script_type, script_content
    )


@mcp.tool()
def delete_rule(
    rule_uid: str = Field(..., description="UID of the rule to delete")
) -> bool:
    """
    Delete an openHAB rule.

    Args:
        rule_uid: UID of the rule to delete
    """
    return openhab_client.delete_rule(rule_uid)


@mcp.tool()
def run_rule_now(
    rule_uid: str = Field(..., description="UID of the rule to run")
) -> bool:
    """
    Run a rule immediately

    Args:
        rule_uid: UID of the rule to run
    """
    return openhab_client.run_rule_now(rule_uid)


@mcp.tool()
def set_rule_enabled(
    rule_uid: str = Field(..., description="UID of the rule to enable"),
    enabled: bool = Field(
        ..., description="Whether to enable (True) or disable (False) the rule"
    ),
) -> bool:
    """
    Enable or disable a rule

    Args:
        rule_uid: UID of the rule to enable/disable
        enabled: Whether to enable (True) or disable (False) the rule
    """
    return openhab_client.set_rule_enabled(rule_uid, enabled)


@mcp.tool()
def list_scripts(
    page: int = Field(
        1,
        description="Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true",
    ),
    page_size: int = Field(15, description="Number of elements per page"),
    sort_order: str = Field("asc", description="Sort order", examples=["asc", "desc"]),
) -> Dict[str, Any]:
    """
    List all openHAB scripts. A script is a rule without a trigger and tag of 'Script'

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 15)
        sort_order: Sort order ("asc" or "desc") (default: "asc")
    """
    return openhab_client.list_scripts(
        page=page, page_size=page_size, sort_order=sort_order
    )


@mcp.tool()
def get_script(
    script_id: str = Field(..., description="ID of the script to get details for"),
) -> Dict[str, Any]:
    """
    Get a specific openHAB script with more details by ID. A script is a rule without a trigger and tag of 'Script'

    Args:
        script_id: ID of the script to get details for
    """
    return openhab_client.get_script(script_id)


@mcp.tool()
def create_script(
    script_id: str = Field(..., description="ID of the script to create"),
    script_type: str = Field(..., description="Type of the script"),
    content: str = Field(..., description="Content of the script"),
) -> Dict[str, Any]:
    """
    Create a new openHAB script. A script is a rule without a trigger and tag of 'Script'.

    Args:
        script_id: ID of the script to create
        script_type: Type of the script
        content: Content of the script
    """
    return openhab_client.create_script(script_id, script_type, content)


@mcp.tool()
def update_script(
    script_id: str = Field(..., description="ID of the script to update"),
    script_type: str = Field(..., description="Type of the script"),
    content: str = Field(..., description="Content of the script"),
) -> Dict[str, Any]:
    """
    Update an existing openHAB script. A script is a rule without a trigger and tag of 'Script'.

    Args:
        script_id: ID of the script to update
        script_type: Type of the script
        content: Content of the script
    """
    return openhab_client.update_script(script_id, script_type, content)


@mcp.tool()
def delete_script(
    script_id: str = Field(..., description="ID of the script to delete"),
) -> bool:
    """
    Delete an openHAB script. A script is a rule without a trigger and tag of 'Script'.

    Args:
        script_id: ID of the script to delete
    """
    return openhab_client.delete_script(script_id)


@mcp.tool()
def list_semantic_tags(
    parent_tag_uid: Optional[str] = Field(
        None, description="UID of the parent tag to filter by"
    ),
    category: Optional[str] = Field(
        None,
        description="Category of the tag to filter by",
        examples=["Location", "Equipment", "Point", "Property"],
    ),
) -> List[Dict[str, Any]]:
    """
    List all openHAB tags, optionally filtered by parent tag and category.
    """
    return openhab_client.list_semantic_tags(parent_tag_uid, category)


@mcp.tool()
def get_semantic_tag(
    tag_uid: str = Field(..., description="UID of the tag to get details for"),
    include_subtags: bool = Field(
        False,
        description="Include subtags in the response",
    ),
) -> Optional[Dict[str, Any]]:
    """
    Get a specific openHAB tag by uid.

    Args:
        tag_uid: UID of the tag to get details for
    """
    return openhab_client.get_semantic_tag(tag_uid, include_subtags)


@mcp.tool()
def get_create_semantic_tag_schema() -> dict:
    """
    Get the JSON schema for creating a tag.
    """
    return Tag.model_json_schema()


@mcp.tool()
def create_semantic_tag(
    tag: Tag = Field(..., description="Tag to create")
) -> Dict[str, Any]:
    """
    Create a new openHAB semantic tag.
    Tags can support multiple levels of hierarchy with the pattern 'parent_child'.
    When adding tags to items only the tag name and not the uid is assigned.

    Args:
        tag: Tag to create
    """
    return openhab_client.create_semantic_tag(tag)


@mcp.tool()
def delete_semantic_tag(
    tag_uid: str = Field(..., description="UID of the tag to delete")
) -> bool:
    """
    Delete an openHAB tag.

    Args:
        tag_uid: UID of the tag to delete
    """
    return openhab_client.delete_semantic_tag(tag_uid)


@mcp.tool()
def add_item_semantic_tag(
    item_name: str = Field(..., description="Name of the item to add the tag to"),
    tag_uid: str = Field(..., description="UID of the tag to add"),
) -> bool:
    """
    Add semantic tag to a specific item

    Args:
        item_name: Name of the item to add the tag to
        tag_uid: UID of the tag to add

    Returns:
        bool: True if the tag was added successfully or raises an error

    Raises:
        ValueError: If the item or tag is not found
    """
    return openhab_client.add_item_semantic_tag(item_name, tag_uid)


@mcp.tool()
def remove_item_semantic_tag(
    item_name: str = Field(..., description="Name of the item to remove tag for"),
    tag_uid: str = Field(..., description="UID of the tag to remove"),
) -> bool:
    """
    Remove semantic tag for a specific openHAB item

    Args:
        item_name: Name of the item to remove the tag from
        tag_uid: UID of the tag to remove

    Returns:
        bool: True if the tag was removed successfully or raises an error

    Raises:
        ValueError: If the item or tag is not found
    """
    return openhab_client.remove_item_semantic_tag(item_name, tag_uid)


@mcp.tool()
def add_item_non_semantic_tag(
    item_name: str = Field(..., description="Name of the item to add the tag to"),
    tag_name: str = Field(..., description="Name of the tag to add"),
) -> bool:
    """
    Add non-semantic tag to a specific item

    Args:
        item_name: Name of the item to add the tag to
        tag_name: Name of the tag to add

    Returns:
        bool: True if the tag was added successfully or raises an error

    Raises:
        ValueError: If the item or tag is not found
    """
    return openhab_client.add_item_non_semantic_tag(item_name, tag_name)


@mcp.tool()
def remove_item_non_semantic_tag(
    item_name: str = Field(..., description="Name of the item to remove tag for"),
    tag_name: str = Field(..., description="Name of the tag to remove"),
) -> bool:
    """
    Remove non-semantic tag for a specific openHAB item

    Args:
        item_name: Name of the item to remove the tag from
        tag_name: Name of the tag to remove

    Returns:
        bool: True if the tag was removed successfully or raises an error

    Raises:
        ValueError: If the item or tag is not found
    """
    return openhab_client.remove_item_non_semantic_tag(item_name, tag_name)


@mcp.tool()
def update_item_members(
    item_name: str = Field(description="Name of the groupitem to update members for"),
    add_members: List[str] = Field(
        default_factory=list, description="List of member item names to add"
    ),
    remove_members: List[str] = Field(
        default_factory=list, description="List of member item names to remove"
    ),
) -> Dict[str, Any]:
    """
    Update the members of a group item by adding and/or removing members.

    Args:
        item_name: Name of the group item to update members for
        add_members: List of member item names to add to the group
        remove_members: List of member item names to remove from the group

    Returns:
        The updated group item
    """
    # Remove members first
    for member_name in remove_members:
        openhab_client.remove_item_member(item_name, member_name)

    # Then add new members
    for member_name in add_members:
        openhab_client.add_item_member(item_name, member_name)

    return openhab_client.list_items(filter_name=item_name, page_size=1)["items"][0]


# Inbox Tools
@mcp.tool()
def list_inbox_things(
    page: int = Field(1, description="Page number (1-based)"),
    page_size: int = Field(15, description="Number of items per page"),
    sort_order: str = Field("asc", description="Sort order (asc or desc)"),
) -> Dict[str, Any]:
    """
    Get a paginated list of discovered things in the inbox

    Args:
        page: Page number (1-based)
        page_size: Number of items per page
        sort_order: Sort order ("asc" or "desc")

    Returns:
        Dictionary containing pagination info and list of inbox items
    """
    return openhab_client.list_inbox_things(
        page=page, page_size=page_size, sort_order=sort_order
    )


@mcp.tool()
def approve_inbox_thing(
    thing_uid: str = Field(..., description="UID of the inbox item to approve"),
    thing_id: str = Field(..., description="ID to assign to the new thing"),
    label: str = Field(..., description="Label for the new thing"),
) -> bool:
    """
    Approve and create a thing from an inbox item

    Args:
        thing_uid: UID of the inbox item
        thing_id: ID to assign to the new thing
        label: Label for the new thing

    Returns:
        bool: True if successful

    Raises:
        ValueError: If the approval fails
    """
    return openhab_client.approve_inbox_thing(thing_uid, thing_id, label)


@mcp.tool()
def ignore_inbox_thing(
    thing_uid: str = Field(..., description="UID of the inbox item to ignore")
) -> bool:
    """
    Mark an inbox item as ignored

    Args:
        thing_uid: UID of the inbox item to ignore

    Returns:
        bool: True if successful

    Raises:
        ValueError: If the operation fails
    """
    return openhab_client.ignore_inbox_thing(thing_uid)


@mcp.tool()
def unignore_inbox_thing(
    thing_uid: str = Field(..., description="UID of the inbox item to unignore")
) -> bool:
    """
    Remove ignore status from an inbox item

    Args:
        thing_uid: UID of the inbox item to unignore

    Returns:
        bool: True if successful

    Raises:
        ValueError: If the operation fails
    """
    return openhab_client.unignore_inbox_thing(thing_uid)


@mcp.tool()
def delete_inbox_thing(
    thing_uid: str = Field(..., description="UID of the inbox item to delete")
) -> bool:
    """
    Delete an item from the inbox

    Args:
        thing_uid: UID of the inbox item to delete

    Returns:
        bool: True if successful

    Raises:
        ValueError: If the deletion fails
    """
    return openhab_client.delete_inbox_thing(thing_uid)


# Template Tools
@mcp.tool()
def list_task_templates(
    query: str = Field("", description="Search query string"),
    tags: List[str] = Field(None, description="Optional list of tags to filter by"),
    limit: int = Field(10, description="Maximum number of results to return"),
    min_relevance: float = Field(0.1, description="Minimum relevance score (0.0 to 1.0)")
) -> List[Dict[str, Any]]:
    """
    Search for task templates matching the query and optional tags. A task template can help to execute
    more complex tasks so make sure to search here before you develop your own plan.
    
    Args:
        query: Search query string
        tags: Optional list of tags to filter by
        limit: Maximum number of results to return
        min_relevance: Minimum relevance score (0.0 to 1.0)
        
    Returns:
        List of task template search results with metadata
    """
    results = template_manager.search_templates(
        query=query,
        tags=tags,
        limit=limit,
        min_relevance=min_relevance
    )
    return [result for result in results]

@mcp.tool()
def get_task_template(template_id: str = Field(..., description="ID of the template to retrieve")) -> Optional[Dict[str, Any]]:
    """
    Get a task template by ID. A task template is a structured process description for recurring tasks.
    If instructed by the user make sure to follow the template instructions as good as possible,
    not to deviate from the step order, skip or modify steps. If confirmation of the user is required
    make sure to ask for permission to continue. If a step fails, follow its on_fail instructions.
    
    Args:
        template_id: ID of the template to retrieve
        
    Returns:
        The template if found, None otherwise
    """
    if template := template_manager.get_template(template_id):
        return template.dict()
    return None

@mcp.tool()
def save_task_template_override(template_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save a task template to the override directory. This can be used to adjust existing templates to the
    user's needs depending on the user's environment. This can also be used to create new templates.
    
    Args:
        template_data: Task template data to save (must include metadata.id)
        
    Returns:
        The saved template
        
    Raises:
        ValueError: If template data is invalid or saving fails
    """
    try:
        # Validate the template data
        template = ProcessTemplate(**template_data)
        
        # Save to override directory
        if template_manager.save_override_template(template):
            # Reload templates to update the cache
            template_manager.reload_templates()
            return template.model_dump()
        else:
            raise ValueError("Failed to save template override")
    except Exception as e:
        raise ValueError(f"Invalid template data: {str(e)}")

@mcp.tool()
def delete_task_template_override(template_id: str = Field(..., description="ID of the template to delete from overrides")) -> bool:
    """
    Delete a task template from the override directory. This can be used to remove templates that
    are no longer needed or to revert to the default template.
    
    Args:
        template_id: ID of the template to delete
        
    Returns:
        bool: True if deleted or didn't exist, False on error
    """
    try:
        success = template_manager.delete_override_template(template_id)
        if success:
            template_manager.reload_templates()
        return success
    except Exception as e:
        raise ValueError(f"Failed to delete template override: {str(e)}")

@mcp.tool()
def get_task_template_schema() -> Dict[str, Any]:
    """
    Get the JSON schema for a task template. This can be used to validate template data before saving.
    
    Returns:
        The JSON schema for a task template, generated from Pydantic models
    """
    # Generate schema from the ProcessTemplate Pydantic model
    schema = ProcessTemplate.model_json_schema()
    
    # Add any additional schema customization if needed
    # For example, you might want to add descriptions or examples
    
    return schema

# Add the template manager to the MCP instance
mcp.template_manager = template_manager

if __name__ == "__main__":
    mcp.run(transport=OPENHAB_MCP_TRANSPORT)
