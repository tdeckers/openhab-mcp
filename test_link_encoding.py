#!/usr/bin/env python3
"""
Test script to verify URL encoding fix for channel UIDs with special characters
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from models import Item, ItemChannelLinkDTO

# Import our client and models
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

    # Test data with special characters (the problematic case from the user)
    test_item_name = "BMW_i4_M50_Total_Distance_Driven"
    test_channel_uid = "mybmw:bev:54a4b9f231:WBY31AW080FP99741:range#mileage"

    print(f"\n--- Testing URL encoding fix for channel UID with special characters ---")
    print(f"Item name: {test_item_name}")
    print(f"Channel UID: {test_channel_uid}")
    print(f"Special characters in UID: colons (:) and hash (#)")

    try:
        # First, ensure the test item exists (create it if it doesn't)
        print(f"\n1. Checking if test item '{test_item_name}' exists...")
        existing_item = client.get_item(test_item_name)

        if not existing_item:
            print(f"   Item doesn't exist, creating it...")
            test_item = Item(
                name=test_item_name,
                type="Number:Length",
                label="BMW i4 M50 Total Distance Driven",
                tags=["Test"],
            )
            created_item = client.create_item(test_item)
            print(f"   ✅ Created item: {created_item.name}")
        else:
            print(f"   ✅ Item already exists: {existing_item.name}")

        # Test create_or_update_link with special characters
        print(f"\n2. Testing create_or_update_link() with special characters...")

        link_data = ItemChannelLinkDTO(
            itemName=test_item_name, channelUID=test_channel_uid, configuration={}
        )

        result = client.create_or_update_link(
            item_name=test_item_name, channel_uid=test_channel_uid, link_data=link_data
        )

        if result:
            print(f"   ✅ Successfully created/updated link!")
        else:
            print(f"   ❌ Failed to create/update link")
            return 1

        # Test get_link with special characters
        print(f"\n3. Testing get_link() with special characters...")
        retrieved_link = client.get_link(test_item_name, test_channel_uid)

        if retrieved_link:
            print(f"   ✅ Successfully retrieved link!")
            print(f"   Item: {retrieved_link.itemName}")
            print(f"   Channel: {retrieved_link.channelUID}")
            print(f"   Editable: {retrieved_link.editable}")
        else:
            print(f"   ❌ Failed to retrieve link")
            return 1

        # Test delete_link with special characters
        print(f"\n4. Testing delete_link() with special characters...")
        delete_result = client.delete_link(test_item_name, test_channel_uid)

        if delete_result:
            print(f"   ✅ Successfully deleted link!")
        else:
            print(f"   ❌ Failed to delete link")
            return 1

        # Verify link is actually deleted
        print(f"\n5. Verifying link was deleted...")
        deleted_link = client.get_link(test_item_name, test_channel_uid)

        if deleted_link is None:
            print(f"   ✅ Link is properly deleted (not found)")
        else:
            print(f"   ❌ Link still exists after deletion")
            return 1

        # Clean up: delete the test item
        print(f"\n6. Cleaning up test item...")
        client.delete_item(test_item_name)
        print(f"   ✅ Test item deleted")

    except Exception as e:
        print(f"   ❌ Error during test: {e}")
        import traceback

        traceback.print_exc()
        return 1

    print(f"\n🎉 All URL encoding tests passed! The fix is working correctly.")
    print(
        f"   Channel UIDs with special characters (: and #) are now properly handled."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
