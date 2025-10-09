#!/usr/bin/env python3
"""
Test script to verify OpenHAB MCP server functionality from command line
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Import our client
from openhab_client import OpenHABClient

# Load environment variables
env_file = Path(".env")
if env_file.exists():
    print(f"Loading environment variables from {env_file}")
    load_dotenv(env_file)
else:
    print("No .env file found, using environment variables or defaults")


def main():
    # Get connection settings
    openhab_url = os.environ.get("OPENHAB_URL", "http://localhost:8080")
    openhab_token = os.environ.get("OPENHAB_API_TOKEN")
    openhab_username = os.environ.get("OPENHAB_USERNAME")
    openhab_password = os.environ.get("OPENHAB_PASSWORD")

    print(f"Testing OpenHAB connection to: {openhab_url}")

    if openhab_token:
        print("Using API token authentication")
    elif openhab_username and openhab_password:
        print("Using username/password authentication")
    else:
        print("Warning: No authentication credentials found!")
        return 1

    # Create client
    client = OpenHABClient(
        base_url=openhab_url,
        api_token=openhab_token,
        username=openhab_username,
        password=openhab_password,
    )

    try:
        print("\n--- Testing list_items() ---")
        items_page = client.list_items(page_size=10)
        items = items_page.items
        pagination = items_page.pagination
        print(
            f"Found {pagination.total_elements} items "
            f"(showing {len(items)} on page {pagination.page}/{max(pagination.total_pages, 1)}):"
        )

        for item in items[:10]:  # Show first 10 items
            print(f"  - {item.name} ({item.type}): {item.state}")
            if item.label:
                print(f"    Label: {item.label}")

        if pagination.has_next:
            remaining = max(
                0,
                pagination.total_elements
                - pagination.page * pagination.page_size,
            )
            if remaining > 0:
                print(f"  ... and {remaining} more items")

    except Exception as e:
        print(f"Error listing items: {e}")
        return 1

    try:
        print("\n--- Testing list_things() ---")
        things_page = client.list_things(page_size=5)
        things = things_page.things
        pagination = things_page.pagination
        print(
            f"Found {pagination.total_elements} things "
            f"(showing {len(things)} on page {pagination.page}/{max(pagination.total_pages, 1)}):"
        )

        for thing in things[:5]:  # Show first 5 things
            status = thing.statusInfo.status if thing.statusInfo else "UNKNOWN"
            print(f"  - {thing.UID} ({thing.thingTypeUID}): {status}")
            if thing.label:
                print(f"    Label: {thing.label}")

        if pagination.has_next:
            remaining = max(
                0,
                pagination.total_elements
                - pagination.page * pagination.page_size,
            )
            if remaining > 0:
                print(f"  ... and {remaining} more things")

    except Exception as e:
        print(f"Error listing things: {e}")
        return 1

    try:
        print("\n--- Testing list_rules() ---")
        rules = client.list_rules()
        print(f"Found {len(rules)} rules:")

        for rule in rules[:5]:  # Show first 5 rules
            print(f"  - {rule.uid}: {rule.name}")
            print(f"    Status: {rule.status}, Visibility: {rule.visibility}")

        if len(rules) > 5:
            print(f"  ... and {len(rules) - 5} more rules")

    except Exception as e:
        print(f"Error listing rules: {e}")
        return 1

    try:
        print("\n--- Testing list_links() ---")
        links = client.list_links()
        print(f"Found {len(links)} item-channel links:")

        for link in links[:10]:  # Show first 10 links
            print(f"  - {link.itemName} -> {link.channelUID}")
            if link.configuration:
                print(f"    Configuration: {link.configuration}")
            print(f"    Editable: {link.editable}")

        if len(links) > 10:
            print(f"  ... and {len(links) - 10} more links")

        # Test filtering by item name if we have links
        if links:
            first_item = links[0].itemName
            print(f"\n--- Testing list_links() filtered by item '{first_item}' ---")
            filtered_links = client.list_links(item_name=first_item)
            print(f"Found {len(filtered_links)} links for item '{first_item}':")
            for link in filtered_links:
                print(f"  - {link.itemName} -> {link.channelUID}")

        # Test get_link() if we have links to test with
        if links:
            test_link = links[0]
            print(
                f"\n--- Testing get_link() for '{test_link.itemName}' -> '{test_link.channelUID}' ---"
            )
            specific_link = client.get_link(test_link.itemName, test_link.channelUID)
            if specific_link:
                print(
                    f"Retrieved link: {specific_link.itemName} -> {specific_link.channelUID}"
                )
                print(f"Configuration: {specific_link.configuration}")
                print(f"Editable: {specific_link.editable}")
            else:
                print("Link not found (unexpected)")

    except Exception as e:
        print(f"Error testing links: {e}")
        return 1

    try:
        print("\n--- Testing get_orphan_links() ---")
        orphan_links = client.get_orphan_links()
        print(f"Found {len(orphan_links)} orphaned links:")

        for link in orphan_links[:5]:  # Show first 5 orphaned links
            print(f"  - {link.itemName} -> {link.channelUID} (orphaned)")
            if link.configuration:
                print(f"    Configuration: {link.configuration}")

        if len(orphan_links) > 5:
            print(f"  ... and {len(orphan_links) - 5} more orphaned links")

    except Exception as e:
        print(f"Error testing orphan links: {e}")
        return 1

    print("\n✅ All tests completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
