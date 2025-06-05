#!/usr/bin/env python3
"""
OpenHAB MCP Server - An MCP server that interacts with a real openHAB instance.

This server uses mcp.server for simplified MCP server implementation and
connects to a real openHAB instance via its REST API.
"""

import os
import sys
import logging
from typing import Callable, Dict, List, Optional, Any
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic import ValidationError
import json

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
    ItemMetadata,
    Link,
    PaginatedLinks,
    Tag,
    Thing,
    ThingDetails,
    PaginatedThings,
    PaginatedItems,
    PaginatedRules,
    RuleDetails,
    ItemPersistence,
)
from openhab_client import OpenHABClient

def custom_error_handler(func: Callable) -> Callable:
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            # Transform Pydantic errors to the expected format
            errors: List[Dict[str, Any]] = []
            for err in e.errors():
                error_detail = {
                    "code": err.get("type", "validation_error"),
                    "expected": "valid value",
                    "received": str(err.get("input", "")),
                    "path": list(err.get("loc", [])),
                    "message": err.get("msg", "")
                }
                errors.append(error_detail)
            # Return the errors as a JSON-formatted string
            return json.dumps(errors)
    return wrapper

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


def __validate_model(model: BaseModel):
    if len(model.model_extra) > 0:
        raise ValueError("Unsupported fields: " + ", ".join(model.model_extra.keys()))


@mcp.tool()
@custom_error_handler
def list_items(
    page: int = Field(
        description="Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true",
        default=1,
    ),
    page_size: int = Field(description="Number of elements per page", default=50),
    sort_by: str = Field(
        description="Field to sort by", examples=["name", "label"], default="name"
    ),
    sort_order: str = Field(
        description="Sort order", examples=["asc", "desc"], default="asc"
    ),
    filter_tag: Optional[str] = Field(
        description="Optional filter items by tag name. All available tags can be retrieved from the `list_tags` tool",
        examples=["Location", "Window", "Light", "FrontDoor"],
        default=None,
    ),
    filter_type: Optional[str] = Field(
        description="Optional filter items by type",
        examples=["Switch", "Group", "String"],
        default=None,
    ),
    filter_name: Optional[str] = Field(
        description="Optional filter items by name. All items that contain the filter value in their name are returned",
        examples=["Kitchen", "LivingRoom", "Bedroom"],
        default=None,
    ),
) -> PaginatedItems:
    """
    Gives a list of openHAB items with only basic information. Use this tool
    to get an overview of your items. Use the `get_item_details` tool to get
    more information about a specific item.

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 50)
        sort_by: Field to sort by (e.g., "name", "label") (default: "name")
        sort_order: Sort order ("asc" or "desc") (default: "asc")
        filter_tag: Optional filter items by tag name. All available tags can be retrieved from the `list_tags` tool
        filter_type: Optional filter items by type
        filter_name: Optional filter items by name. All items that contain the filter value in their name are returned
    """
    return openhab_client.list_items(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        filter_tag=filter_tag,
        filter_type=filter_type,
        filter_name=filter_name,
    )


@mcp.tool()
@custom_error_handler
def get_item_details(
    item_name: str = Field(description="Name of the item to get details for"),
) -> Optional[ItemDetails]:
    """
    Gives complete details of an openHAB item, e.g. its
    members (if it is a group item), metadata, commandDescription,
    stateDescription and unitSymbol.

    Use this tool when you need additional information about a specific item
    that you have received from `list_items`.

    Args:
        item_name: Name of the item to get details for
    """
    item = openhab_client.get_item_details(item_name)
    return item


@mcp.tool()
@custom_error_handler
def create_item_metadata(
    item_name: str = Field(description="Name of the item to create metadata for"),
    namespace: str = Field(description="Namespace of the metadata"),
    metadata: ItemMetadata = Field(description="Metadata to create"),
) -> ItemDetails:
    """Create new metadata for a specific openHAB item"""
    __validate_model(metadata)
    return openhab_client.create_item_metadata(item_name, namespace, metadata)


@mcp.tool()
@custom_error_handler
def update_item_metadata(
    item_name: str = Field(description="Name of the item to update metadata for"),
    namespace: str = Field(description="Namespace of the metadata"),
    metadata: ItemMetadata = Field(description="Metadata to update"),
) -> ItemDetails:
    """Update metadata for a specific openHAB item"""
    __validate_model(metadata)
    return openhab_client.update_item_metadata(item_name, namespace, metadata)


@mcp.tool()
@custom_error_handler
def create_item(
    item: ItemDetails = Field(description="Item details to create"),
) -> ItemDetails:
    """Create a new openHAB item"""
    __validate_model(item)
    created_item = openhab_client.create_item(item)
    return created_item


@mcp.tool()
@custom_error_handler
def update_item(
    item: ItemDetails = Field(description="Item details to update"),
) -> ItemDetails:
    """
    Update an existing openHAB item

    Args:
        item: Item details to update
    """
    __validate_model(item)
    updated_item = openhab_client.update_item(item)
    return updated_item


@mcp.tool()
@custom_error_handler
def delete_item(
    item_name: str = Field(description="Name of the item to delete"),
) -> bool:
    """Delete an openHAB item"""
    return openhab_client.delete_item(item_name)


@mcp.tool()
@custom_error_handler
def update_item_state(
    item_name: str = Field(description="Name of the item to update state for"),
    state: str = Field(
        description="State to update. Allowed states depend on the item type",
        examples=["ON", "OFF", "140.5", "20 kWH", "2025-06-03T22:21:13.123Z"],
    ),
) -> Item:
    """
    Update the state of an openHAB item

    Args:
        item_name: Name of the item to update state for
        state: State to update. Allowed states depend on the item type
    """
    updated_item = openhab_client.update_item_state(item_name, state)
    return updated_item


@mcp.tool()
@custom_error_handler
def get_item_persistence(
    item_name: str = Field(description="Name of the item to get persistence for"),
    start: str = Field(
        description="Start time in zulu time format [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']",
        examples=["2025-06-03T22:21:13.123Z"],
    ),
    end: str = Field(
        description="End time in zulu time format [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']",
        examples=["2025-06-03T22:21:13.123Z"],
    ),
) -> ItemPersistence:
    """
    Get the persistence values of an openHAB item between start and end in zulu time format
    [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']

    Args:
        item_name: Name of the item to get persistence for
        start: Start time in zulu time format [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']
        end: End time in zulu time format [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']
    """
    persistence = openhab_client.get_item_persistence(item_name, start, end)
    return persistence


@mcp.tool()
@custom_error_handler
def list_locations(
    page: int = Field(
        description="Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true",
        default=1,
    ),
    page_size: int = Field(description="Number of elements per page", default=50),
    sort_by: str = Field(
        description="Field to sort by", examples=["name", "label"], default="name"
    ),
    sort_order: str = Field(
        description="Sort order", examples=["asc", "desc"], default="asc"
    ),
) -> PaginatedItems:
    """
    Locations are items with a tag of 'Location'. List openHAB locations with basic information
    with pagination. Use the `get_item_details` tool to get more information about a specific
    location item.

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 50)
        sort_by: Field to sort by (e.g., "name", "label") (default: "name")
        sort_order: Sort order ("asc" or "desc") (default: "asc")
    """
    locations = openhab_client.list_locations(
        page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
    )
    return locations

@mcp.tool()
@custom_error_handler
def list_things(
    page: int = Field(
        description="Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true",
        default=1,
    ),
    page_size: int = Field(description="Number of elements per page", default=50),
    sort_by: str = Field(
        description="Field to sort by", examples=["UID", "label"], default="UID"
    ),
    sort_order: str = Field(
        description="Sort order", examples=["asc", "desc"], default="asc"
    ),
) -> PaginatedThings:
    """
    List openHAB things with basic information with pagination. Use the `get_thing_details` tool to get
    more information about a specific thing.

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 50)
        sort_by: Field to sort by (e.g., "UID", "label") (default: "UID")
        sort_order: Sort order ("asc" or "desc") (default: "asc")
    """
    return openhab_client.list_things(
        page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
    )


@mcp.tool()
@custom_error_handler
def get_thing_details(
    thing_uid: str = Field(description="UID of the thing to get details for"),
) -> Optional[ThingDetails]:
    """
    Get a specific openHAB thing with more details by UID. Use the `get_thing_details` tool to get
    more information about a specific thing.

    Args:
        thing_uid: UID of the thing to get details for
    """
    thing_details = openhab_client.get_thing_details(thing_uid)
    return thing_details


@mcp.tool()
@custom_error_handler
def create_thing(
    thing: Thing = Field(description="Thing to create"),
) -> Optional[ThingDetails]:
    """
    Create a new openHAB thing.

    Args:
        thing: Thing to create
    """
    __validate_model(thing)
    created_thing = openhab_client.create_thing(thing)
    return created_thing


@mcp.tool()
@custom_error_handler
def update_thing(
    thing: Thing = Field(description="Thing to update"),
) -> Optional[ThingDetails]:
    """
    Update an existing openHAB thing.

    Args:
        thing: Thing to update
    """
    __validate_model(thing)
    updated_thing = openhab_client.update_thing(thing)
    return updated_thing


@mcp.tool()
@custom_error_handler
def delete_thing(
    thing_uid: str = Field(description="UID of the thing to delete"),
) -> bool:
    """
    Delete an openHAB thing.

    Args:
        thing_uid: UID of the thing to delete
    """
    return openhab_client.delete_thing(thing_uid)


@mcp.tool()
@custom_error_handler
def list_rules(
    page: int = Field(
        description="Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true",
        default=1,
    ),
    page_size: int = Field(description="Number of elements per page", default=50),
    sort_by: str = Field(
        description="Field to sort by", examples=["UID", "label"], default="UID"
    ),
    sort_order: str = Field(
        description="Sort order", examples=["asc", "desc"], default="asc"
    ),
    filter_tag: Optional[str] = Field(
        description="Filter rules by tag (default: None)", default=None
    ),
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
@custom_error_handler
def get_rule_details(
    rule_uid: str = Field(description="UID of the rule to get details for"),
) -> Optional[RuleDetails]:
    """
    Get a specific openHAB rule with more details by UID.

    Args:
        rule_uid: UID of the rule to get details for
    """
    rule_details = openhab_client.get_rule_details(rule_uid)
    return rule_details


@mcp.tool()
@custom_error_handler
def list_scripts(
    page: int = Field(
        description="Page number of paginated result set. Page index starts with 1. There are more items when `has_next` is true",
        default=1,
    ),
    page_size: int = Field(description="Number of elements per page", default=50),
    sort_by: str = Field(
        description="Field to sort by", examples=["UID", "label"], default="UID"
    ),
    sort_order: str = Field(
        description="Sort order", examples=["asc", "desc"], default="asc"
    ),
) -> PaginatedRules:
    """
    List all openHAB scripts. A script is a rule without a trigger and tag of 'Script'

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
@custom_error_handler
def get_script_details(
    script_id: str = Field(description="ID of the script to get details for"),
) -> Optional[RuleDetails]:
    """
    Get a specific openHAB script with more details by ID. A script is a rule without a trigger and tag of 'Script'

    Args:
        script_id: ID of the script to get details for
    """
    script_details = openhab_client.get_script_details(script_id)
    return script_details


@mcp.tool()
@custom_error_handler
def update_rule(
    rule_uid: str = Field(description="UID of the rule to update"),
    rule_updates: Dict[str, Any] = Field(
        description="Partial updates to apply to the rule"
    ),
) -> RuleDetails:
    """
    Update an existing openHAB rule with partial updates.

    Args:
        rule_uid: UID of the rule to update
        rule_updates: Partial updates to apply to the rule
    """
    updated_rule = openhab_client.update_rule(rule_uid, rule_updates)
    return updated_rule


@mcp.tool()
@custom_error_handler
def update_rule_script_action(
    rule_uid: str = Field(description="UID of the rule to update"),
    action_id: str = Field(description="ID of the action to update"),
    script_type: str = Field(description="Type of the script"),
    script_content: str = Field(description="Content of the script"),
) -> RuleDetails:
    """
    Update a script action in an openHAB rule.

    Args:
        rule_uid: UID of the rule to update
        action_id: ID of the action to update
        script_type: Type of the script
        script_content: Content of the script
    """
    updated_rule = openhab_client.update_rule_script_action(
        rule_uid, action_id, script_type, script_content
    )
    return updated_rule


@mcp.tool()
@custom_error_handler
def create_rule(rule: RuleDetails = Field(description="Rule to create")) -> RuleDetails:
    """
    Create a new openHAB rule.

    Args:
        rule: Rule to create
    """
    __validate_model(rule)
    created_rule = openhab_client.create_rule(rule)
    return created_rule


@mcp.tool()
@custom_error_handler
def delete_rule(rule_uid: str = Field(description="UID of the rule to delete")) -> bool:
    """
    Delete an openHAB rule.

    Args:
        rule_uid: UID of the rule to delete
    """
    return openhab_client.delete_rule(rule_uid)


@mcp.tool()
@custom_error_handler
def create_script(
    script_id: str = Field(description="ID of the script to create"),
    script_type: str = Field(description="Type of the script"),
    content: str = Field(description="Content of the script"),
) -> RuleDetails:
    """
    Create a new openHAB script. A script is a rule without a trigger and tag of 'Script'. 

    Args:
        script_id: ID of the script to create
        script_type: Type of the script
        content: Content of the script
    """
    created_script = openhab_client.create_script(script_id, script_type, content)
    return created_script


@mcp.tool()
@custom_error_handler
def update_script(
    script_id: str = Field(description="ID of the script to update"),
    script_type: str = Field(description="Type of the script"),
    content: str = Field(description="Content of the script"),
) -> RuleDetails:
    """
    Update an existing openHAB script. A script is a rule without a trigger and tag of 'Script'.

    Args:
        script_id: ID of the script to update
        script_type: Type of the script
        content: Content of the script
    """
    updated_script = openhab_client.update_script(script_id, script_type, content)
    return updated_script


@mcp.tool()
@custom_error_handler
def delete_script(
    script_id: str = Field(description="ID of the script to delete"),
) -> bool:
    """
    Delete an openHAB script. A script is a rule without a trigger and tag of 'Script'.

    Args:
        script_id: ID of the script to delete
    """
    return openhab_client.delete_script(script_id)


@mcp.tool()
@custom_error_handler
def run_rule_now(rule_uid: str = Field(description="UID of the rule to run")) -> bool:
    """
    Run an openHAB rule immediately.

    Args:
        rule_uid: UID of the rule to run
    """
    return openhab_client.run_rule_now(rule_uid)


@mcp.tool()
@custom_error_handler
def list_tags(
    parent_tag_uid: Optional[str] = Field(
        description="UID of the parent tag to filter by"
    ),
) -> List[Tag]:
    """
    List all openHAB tags, optionally filtered by parent tag.

    Args:
        parent_tag_uid: UID of the parent tag to filter by
    """
    tags = openhab_client.list_tags(parent_tag_uid)
    return tags


@mcp.tool()
@custom_error_handler
def get_tag(
    tag_uid: str = Field(description="UID of the tag to get details for"),
) -> Optional[Tag]:
    """
    Get a specific openHAB tag by uid.

    Args:
        tag_uid: UID of the tag to get details for
    """
    tag = openhab_client.get_tag(tag_uid)
    return tag


@mcp.tool()
@custom_error_handler
def create_tag(tag: Tag = Field(description="Tag to create")) -> Tag:
    """
    Create a new openHAB tag.
    Tags can support multiple levels of hierarchy with the pattern 'parent_child'.
    When adding tags to items only the tag name and not the uid is assigned.

    Args:
        tag: Tag to create
    """
    __validate_model(tag)
    created_tag = openhab_client.create_tag(tag)
    return created_tag


@mcp.tool()
@custom_error_handler
def delete_tag(tag_uid: str = Field(description="UID of the tag to delete")) -> bool:
    """
    Delete an openHAB tag.

    Args:
        tag_uid: UID of the tag to delete
    """
    return openhab_client.delete_tag(tag_uid)


@mcp.tool()
@custom_error_handler
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
) -> PaginatedLinks:
    """
    List all openHAB item to thing links, optionally filtered by item name with pagination.

    Args:
        page: 1-based page number (default: 1)
        page_size: Number of elements per page (default: 50)
        sort_order: Sort order ("asc" or "desc") (default: "asc")
        item_name: Optional filter links by item name (default: None)
    """
    links = openhab_client.list_links(page, page_size, sort_order, item_name)
    return links


@mcp.tool()
@custom_error_handler
def get_link(
    item_name: str = Field(description="Name of the item to get link for"),
    channel_uid: str = Field(description="UID of the channel to get link for"),
) -> Optional[Link]:
    """
    Get a specific openHAB item to thing link by item name and channel UID.

    Args:
        item_name: Name of the item to get link for
        channel_uid: UID of the channel to get link for
    """
    link = openhab_client.get_link(item_name, channel_uid)
    return link


@mcp.tool()
@custom_error_handler
def create_link(link: Link = Field(description="Link to create")) -> Link:
    """
    Create a new openHAB item to thing link.

    Args:
        link: Link to create
    """
    __validate_model(link)
    created_link = openhab_client.create_link(link)
    return created_link


@mcp.tool()
@custom_error_handler
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
    return openhab_client.delete_link(item_name, channel_uid)


@mcp.tool()
@custom_error_handler
def update_link(link: Link = Field(description="Link to update")) -> Link:
    """
    Update an existing openHAB item to thing link.

    Args:
        link: Link to update
    """
    __validate_model(link)
    updated_link = openhab_client.update_link(link)
    return updated_link


if __name__ == "__main__":
    mcp.run(transport=OPENHAB_MCP_TRANSPORT)
