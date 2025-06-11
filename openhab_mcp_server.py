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
logging.basicConfig(level=logging.DEBUG)

# Import the MCP server implementation
from mcp.server import FastMCP
from mcp.types import TextContent

# Import our modules
from models import (
    CreateItem,
    Item,
    ItemMetadata,
    Link,
    Tag,
    Thing,
    RuleDetails,
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
OPENHAB_GENERATE_UIDS = os.environ.get("OPENHAB_GENERATE_UIDS", "false").lower() in [
    "true",
    "1",
    "t",
]
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
    generate_uids=OPENHAB_GENERATE_UIDS,
)


def _set_additional_properties_false(schema: dict) -> Dict[str, Any]:
    """
    Recursively sets additionalProperties to False for all objects in a JSON schema.
    
    Args:
        schema: The JSON schema to modify
        
    Returns:
        The modified schema with additionalProperties set to False
    """
    if not isinstance(schema, dict):
        return schema
        
    # Create a new dict to avoid modifying the original during iteration
    result = {}
    
    for key, value in schema.items():
        if key == 'additionalProperties' and isinstance(schema, dict):
            result[key] = False
        elif isinstance(value, dict):
            result[key] = _set_additional_properties_false(value)
        elif isinstance(value, list):
            result[key] = [
                _set_additional_properties_false(item) if isinstance(item, dict) else item 
                for item in value
            ]
        else:
            result[key] = value
    
    return result


@mcp.tool()
def list_items(
    page: int = Field(
        description="Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true",
        default=1,
    ),
    page_size: int = Field(description="Number of elements shown per page", default=50),
    sort_order: str = Field(
        description="Sort order", examples=["asc", "desc"], default="asc"
    ),
    filter_tag: str = Field(
        description="Optional filter items by tag (either a non-semantic tag or the name of a semantic tag). All available semantic tags can be retrieved from the `list_tags` tool",
        examples=["Location", "Window", "Light", "FrontDoor"],
        default="",
    ),
    filter_type: str = Field(
        description="Optional filter items by type",
        examples=["Switch", "Group", "String", "DateTime"],
        default="",
    ),
    filter_name: str = Field(
        description="Optional filter items by name. All items that contain the filter value in their name are returned",
        examples=["Kitchen", "LivingRoom", "Bedroom"],
        default="",
    ),
    filter_fields: List[str] = Field(
        description="Optional filter items by fields. Item name will always be included by default.",
        examples=["name", "label", "type", "semantic_tags", "non_semantic_tags"],
        default=[],
    ),
) -> Dict[str, Any]:
    """
    Gives a list of openHAB items with only basic information. Use this tool
    to get an overview of your items. Use the `get_item_details` tool to get
    more information about a specific item.
    """
    try:
        return openhab_client.list_items(
            page=page,
            page_size=page_size,
            sort_order=sort_order,
            filter_tag=filter_tag,
            filter_type=filter_type,
            filter_name=filter_name,
            filter_fields=filter_fields,
        )
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def get_create_item_metadata_schema() -> Dict[str, Any]:
    """
    Get the JSON schema for creating item metadata.
    """
    schema = ItemMetadata.model_json_schema()
    schema = _set_additional_properties_false(schema)
    return schema


@mcp.tool()
def create_item_metadata(
    item_name: str = Field(description="Name of the item to create metadata for"),
    namespace: str = Field(description="Namespace of the metadata"),
    metadata: ItemMetadata = Field(description="Metadata to create"),
) -> Dict[str, Any]:
    """Create new metadata for a specific openHAB item"""
    try:
        metadata.raise_for_errors()
        return openhab_client.create_item_metadata(item_name, namespace, metadata)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}

@mcp.tool()
def delete_item_metadata(
    item_name: str = Field(description="Name of the item to delete metadata for"),
    namespace: str = Field(description="Namespace of the metadata"),
) -> bool:
    """Delete metadata for a specific openHAB item"""
    try:
        return openhab_client.delete_item_metadata(item_name, namespace)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]} 

@mcp.tool()
def update_item_metadata(
    item_name: str = Field(description="Name of the item to update metadata for"),
    namespace: str = Field(description="Namespace of the metadata"),
    metadata: ItemMetadata = Field(description="Metadata to update"),
) -> Dict[str, Any]:
    """Update metadata for a specific openHAB item"""
    try:
        # Validate that the namespace is not 'semantics'
        if namespace == "semantics":
            raise ValueError("The 'semantics' namespace is a reserved namespace for openHAB semantic tags. Please assign tags to change the item semantics.")
            
        metadata.raise_for_errors()
        return openhab_client.update_item_metadata(item_name, namespace, metadata)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}

@mcp.tool()
def delete_item_semantic_tag(
    item_name: str = Field(description="Name of the item to delete tag for"),
    tag_uid: str = Field(description="UID of the tag to delete"),
) -> bool:
    """Delete tag for a specific openHAB item"""
    try:
        return openhab_client.delete_item_semantic_tag(item_name, tag_uid)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}
    
@mcp.tool()
def delete_item_non_semantic_tag(
    item_name: str = Field(description="Name of the item to delete tag for"),
    tag_name: str = Field(description="Name of the tag to delete"),
) -> bool:
    """Delete tag for a specific openHAB item"""
    try:
        return openhab_client.delete_item_non_semantic_tag(item_name, tag_name)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}

@mcp.tool()
def get_create_item_schema() -> Dict[str, Any]:
    """
    Get the JSON schema for creating an item.
    """
    schema = CreateItem.model_json_schema()
    schema = _set_additional_properties_false(schema)
    return schema


@mcp.tool()
def create_item(
    item: CreateItem = Field(description="Item details to create"),
) -> Dict[str, Any]:
    """Create a new openHAB item"""
    try:
        item.raise_for_errors()
        return openhab_client.create_item(item)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def update_item(
    item: Item = Field(description="Item details to update"),
) -> Dict[str, Any]:
    """
    Update an existing openHAB item

    Args:
        item: Item details to update
    """
    try:
        item.raise_for_errors()
        return openhab_client.update_item(item)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def delete_item(
    item_name: str = Field(description="Name of the item to delete"),
) -> bool:
    """Delete an openHAB item"""
    try:
        return openhab_client.delete_item(item_name)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def update_item_state(
    item_name: str = Field(description="Name of the item to update state for"),
    state: str = Field(
        description="State to update the item to as string. Type conversion must be possible for the item type",
        examples=["ON", "OFF", "140.5", "20 kWH", "2025-06-03T22:21:13.123Z", "Text"],
    ),
) -> Dict[str, Any]:
    """
    Update the state of an openHAB item

    Args:
        item_name: Name of the item to update state for
        state: State to update the item to. Allowed states depend on the item type
    """
    try:
        return openhab_client.update_item_state(item_name, state)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def get_item_persistence(
    item_name: str = Field(description="Name of the item to get persistence for"),
    start: str = Field(
        description="Start time in UTC/Zulu time format [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']",
        examples=["2025-06-03T22:21:13.123Z"],
    ),
    end: str = Field(
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
    try:
        return openhab_client.get_item_persistence(item_name, start, end)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def list_things(
    page: int = Field(
        description="Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true",
        default=1,
    ),
    page_size: int = Field(description="Number of elements per page", default=50),
    sort_order: str = Field(
        description="Sort order", examples=["asc", "desc"], default="asc"
    ),
) -> Dict[str, Any]:
    """
    List openHAB things with basic information with pagination. Use the `get_thing_details` tool to get
    more information about a specific thing.

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 50)
        sort_order: Sort order ("asc" or "desc") (default: "asc")
    """
    try:
        return openhab_client.list_things(
            page=page, page_size=page_size, sort_order=sort_order
        )
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def get_thing_channels(
    thing_uid: str = Field(description="UID of the thing to get details for"),
    linked_only: bool = Field(description="If True, only return channels with linked items", default=False),
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


@mcp.tool()
def get_create_thing_schema() -> Dict[str, Any]:
    """
    Get the JSON schema for creating a thing.
    """
    schema = Thing.model_json_schema()
    schema = _set_additional_properties_false(schema)
    return schema


@mcp.tool()
def create_thing(
    thing: Thing = Field(description="Thing to create"),
) -> Dict[str, Any]:
    """
    Create a new openHAB thing.

    Args:
        thing: Thing to create
    """
    try:
        thing.raise_for_errors()
        return openhab_client.create_thing(thing)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def update_thing(
    thing: Thing = Field(description="Thing to update"),
) -> Dict[str, Any]:
    """
    Update an existing openHAB thing.

    Args:
        thing: Thing to update
    """
    try:
        thing.raise_for_errors()
        return openhab_client.update_thing(thing)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def delete_thing(
    thing_uid: str = Field(description="UID of the thing to delete"),
) -> bool:
    """
    Delete an openHAB thing.

    Args:
        thing_uid: UID of the thing to delete
    """
    try:
        return openhab_client.delete_thing(thing_uid)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def list_rules(
    page: int = Field(
        description="Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true",
        default=1,
    ),
    page_size: int = Field(description="Number of elements per page", default=50),
    sort_order: str = Field(
        description="Sort order", examples=["asc", "desc"], default="asc"
    ),
    filter_tag: Optional[str] = Field(
        description="Filter rules by tag (default: None)", default=None
    ),
) -> Dict[str, Any]:
    """
    List openHAB rules with basic information with pagination

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 50)
        sort_order: Sort order ("asc" or "desc") (default: "asc")
        filter_tag: Filter rules by tag (default: None)
    """
    try:
        return openhab_client.list_rules(
            page=page,
            page_size=page_size,
            sort_order=sort_order,
            filter_tag=filter_tag,
        )
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def get_rule_details(
    rule_uid: str = Field(description="UID of the rule to get details for"),
) -> Dict[str, Any]:
    """
    Get a specific openHAB rule with more details by UID.

    Args:
        rule_uid: UID of the rule to get details for
    """
    try:
        return openhab_client.get_rule_details(rule_uid)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def list_scripts(
    page: int = Field(
        description="Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true",
        default=1,
    ),
    page_size: int = Field(description="Number of elements per page", default=50),
    sort_order: str = Field(
        description="Sort order", examples=["asc", "desc"], default="asc"
    ),
) -> Dict[str, Any]:
    """
    List all openHAB scripts. A script is a rule without a trigger and tag of 'Script'

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 15)
        sort_order: Sort order ("asc" or "desc") (default: "asc")
    """
    try:
        return openhab_client.list_scripts(
            page=page, page_size=page_size, sort_order=sort_order
        )
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def get_script_details(
    script_id: str = Field(description="ID of the script to get details for"),
) -> Dict[str, Any]:
    """
    Get a specific openHAB script with more details by ID. A script is a rule without a trigger and tag of 'Script'

    Args:
        script_id: ID of the script to get details for
    """
    try:
        return openhab_client.get_script_details(script_id)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def update_rule(
    rule_uid: str = Field(description="UID of the rule to update"),
    rule_updates: Dict[str, Any] = Field(
        description="Partial updates to apply to the rule"
    ),
) -> Dict[str, Any]:
    """
    Update an existing openHAB rule with partial updates.

    Args:
        rule_uid: UID of the rule to update
        rule_updates: Partial updates to apply to the rule
    """
    try:
        return openhab_client.update_rule(rule_uid, rule_updates)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def update_rule_script_action(
    rule_uid: str = Field(description="UID of the rule to update"),
    action_id: str = Field(description="ID of the action to update"),
    script_type: str = Field(description="Type of the script"),
    script_content: str = Field(description="Content of the script"),
) -> Dict[str, Any]:
    """
    Update a script action in an openHAB rule.

    Args:
        rule_uid: UID of the rule to update
        action_id: ID of the action to update
        script_type: Type of the script
        script_content: Content of the script
    """
    try:
        return openhab_client.update_rule_script_action(
            rule_uid, action_id, script_type, script_content
        )
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def get_create_rule_schema() -> dict:
    """
    Get the JSON schema for creating a rule.
    """
    schema = RuleDetails.model_json_schema()
    schema = _set_additional_properties_false(schema)
    return schema


@mcp.tool()
def create_rule(rule: RuleDetails = Field(description="Rule to create")) -> Dict[str, Any]:
    """
    Create a new openHAB rule.

    Args:
        rule: Rule to create
    """
    try:
        rule.raise_for_errors()
        return openhab_client.create_rule(rule)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def delete_rule(rule_uid: str = Field(description="UID of the rule to delete")) -> bool:
    """
    Delete an openHAB rule.

    Args:
        rule_uid: UID of the rule to delete
    """
    try:
        return openhab_client.delete_rule(rule_uid)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def get_create_script_schema() -> dict:
    """
    Get the JSON schema for creating a script.
    """
    schema = RuleDetails.model_json_schema()
    schema = _set_additional_properties_false(schema)
    return schema


@mcp.tool()
def create_script(
    script_id: str = Field(description="ID of the script to create"),
    script_type: str = Field(description="Type of the script"),
    content: str = Field(description="Content of the script"),
) -> Dict[str, Any]:
    """
    Create a new openHAB script. A script is a rule without a trigger and tag of 'Script'.

    Args:
        script_id: ID of the script to create
        script_type: Type of the script
        content: Content of the script
    """
    try:
        return openhab_client.create_script(script_id, script_type, content)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def update_script(
    script_id: str = Field(description="ID of the script to update"),
    script_type: str = Field(description="Type of the script"),
    content: str = Field(description="Content of the script"),
) -> Dict[str, Any]:
    """
    Update an existing openHAB script. A script is a rule without a trigger and tag of 'Script'.

    Args:
        script_id: ID of the script to update
        script_type: Type of the script
        content: Content of the script
    """
    try:
        return openhab_client.update_script(script_id, script_type, content)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


def delete_script(
    script_id: str = Field(description="ID of the script to delete"),
) -> bool:
    """
    Delete an openHAB script. A script is a rule without a trigger and tag of 'Script'.

    Args:
        script_id: ID of the script to delete
    """
    try:
        return openhab_client.delete_script(script_id)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def run_rule_now(rule_uid: str = Field(description="UID of the rule to run")) -> bool:
    """
    Run an openHAB rule immediately.

    Args:
        rule_uid: UID of the rule to run
    """
    try:
        return openhab_client.run_rule_now(rule_uid)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def list_tags(
    parent_tag_uid: Optional[str] = Field(
        description="UID of the parent tag to filter by",
        default=None,
    ),
    category: Optional[str] = Field(
        description="Category of the tag to filter by",
        examples=["Location", "Equipment", "Point", "Property"],
        default=None,
    ),
) -> List[Dict[str, Any]]:
    """
    List all openHAB tags, optionally filtered by parent tag and category.
    """
    try:
        return openhab_client.list_tags(parent_tag_uid, category)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def get_tag(
    tag_uid: str = Field(description="UID of the tag to get details for"),
    include_subtags: bool = Field(
        description="Include subtags in the response",
        default=False,
    ),
) -> Optional[Dict[str, Any]]:
    """
    Get a specific openHAB tag by uid.

    Args:
        tag_uid: UID of the tag to get details for
    """
    try:
        return openhab_client.get_tag(tag_uid, include_subtags)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def get_create_tag_schema() -> dict:
    """
    Get the JSON schema for creating a tag.
    """
    schema = Tag.model_json_schema()
    schema = _set_additional_properties_false(schema)
    return schema


@mcp.tool()
def create_semantic_tag(tag: Tag = Field(description="Tag to create")) -> Dict[str, Any]:
    """
    Create a new openHAB semantic tag.
    Tags can support multiple levels of hierarchy with the pattern 'parent_child'.
    When adding tags to items only the tag name and not the uid is assigned.

    Args:
        tag: Tag to create
    """
    try:
        tag.raise_for_errors()
        created_tag = openhab_client.create_semantic_tag(tag)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}
    return created_tag


@mcp.tool()
def delete_tag(tag_uid: str = Field(description="UID of the tag to delete")) -> bool:
    """
    Delete an openHAB tag.

    Args:
        tag_uid: UID of the tag to delete
    """
    try:
        openhab_client.delete_tag(tag_uid)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}
    return True


@mcp.tool()
def list_links(
    page: int = Field(
        description="Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true",
        default=1,
    ),
    page_size: int = Field(description="Number of elements per page", default=50),
    sort_order: str = Field(
        description="Sort order", examples=["asc", "desc"], default="asc"
    ),
    item_name: Optional[str] = Field(
        description="Optional filter links by item name", default=None
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
    try:
        links = openhab_client.list_links(page, page_size, sort_order, item_name)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}
    return links


@mcp.tool()
def get_link(
    item_name: str = Field(description="Name of the item to get link for"),
    channel_uid: str = Field(description="UID of the channel to get link for"),
) -> Optional[Dict[str, Any]]:
    """
    Get a specific openHAB item to thing link by item name and channel UID.

    Args:
        item_name: Name of the item to get link for
        channel_uid: UID of the channel to get link for
    """
    try:
        link = openhab_client.get_link(item_name, channel_uid)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}
    return link


@mcp.tool()
def create_link(link: Link = Field(description="Link to create")) -> Dict[str, Any]:
    """
    Create a new openHAB item to thing link.

    Args:
        link: Link to create
    """
    try:
        created_link = openhab_client.create_link(link)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}
    return created_link


@mcp.tool()
def delete_link(
    item_name: str = Field(description="Name of the item to delete link for"),
    channel_uid: str = Field(description="UID of the channel to delete link for"),
) -> bool:
    """
    Delete an openHAB item to thing link.

    Args:
        item_name: Name of the item to delete link for
        channel_uid: UID of the channel to delete link for
    """
    try:
        return openhab_client.delete_link(item_name, channel_uid)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}


@mcp.tool()
def update_link(link: Link = Field(description="Link to update")) -> Dict[str, Any]:
    """
    Update an existing openHAB item to thing link.

    Args:
        link: Link to update
    """
    try:
        updated_link = openhab_client.update_link(link)
    except Exception as e:
        return {"isError": True, "content": [TextContent(type="text", text=str(e))]}
    return updated_link


if __name__ == "__main__":
    mcp.run(transport=OPENHAB_MCP_TRANSPORT)
