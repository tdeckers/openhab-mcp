import unittest
import time
from typing import Dict, Any, List
from openhab_client import OpenHABClient
from models import ItemCreate, ItemMetadata, Tag, TagCategoryEnum, ItemUpdate

class TestOpenHABItems(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize the OpenHAB client before running tests"""
        cls.client = OpenHABClient(
            base_url="https://openhab.amfthome.org",  # Update with your OpenHAB URL
            api_token="oh.admintoken.CJpWSex2w3OSDOCUyPYy5qt9YbqoJkB4G4AggnAub1TUiIKEWyV2MsRoJGmE3DRlvzJojwp9pyKQ622Yig"  # Update with your API token or use username/password
        )
        # Prefix for test items to easily identify and clean them up
        cls.test_prefix = "TestItem_"
        
    def setUp(self):
        """Run before each test method"""
        # Ensure we start with a clean state
        self.cleanup_test_items()
        
    def tearDown(self):
        """Run after each test method"""
        self.cleanup_test_items()
        
    def cleanup_test_items(self):
        """Clean up all test items"""
        try:
            items = self.client.list_items().get("items", [])
            for item in items:
                if item["name"].startswith(self.test_prefix):
                    self.client.delete_item(item["name"])
        except Exception as e:
            print(f"Warning: Failed to clean up test items: {e}")

    def create_test_item(self, name_suffix: str, item_type: str, **kwargs) -> Dict[str, Any]:
        """Helper method to create a test item"""
        item_name = f"{self.test_prefix}{name_suffix}"
        item = ItemCreate(
            name=item_name,
            type=item_type,
            label=f"Test {name_suffix}",
            **kwargs
        )
        return self.client.create_item(item)
        
    def create_test_group_item(self, name_suffix: str, item_type: str, members: List[str] = None, **kwargs) -> Dict[str, Any]:
        """Helper method to create a test group item"""
        item_name = f"{self.test_prefix}Group_{name_suffix}"
        group_item = ItemCreate(
            name=item_name,
            type=item_type,
            label=f"Test Group {name_suffix}",
            **kwargs
        )
        return self.client.create_item(group_item)
        
    def test_create_and_delete_item(self):
        """Test creating and deleting a simple item"""
        # Create a test switch item
        item_name = f"{self.test_prefix}Switch1"
        item = self.create_test_item("Switch1", "Switch")
        self.assertEqual(item["name"], item_name)
        self.assertEqual(item["type"], "Switch")
        
        # Verify the item exists
        items = self.client.list_items(filter_name=item_name).get("items", [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], item_name)
        
        # Delete the item
        result = self.client.delete_item(item_name)
        self.assertTrue(result)
        
        # Verify the item was deleted
        items = self.client.list_items(filter_name=item_name).get("items", [])
        self.assertEqual(len(items), 0)
        
    def test_update_item_metadata(self):
        """Test updating item metadata"""
        # Create a test item
        item = self.create_test_item("Dimmer1", "Dimmer")
        item_name = item["name"]
        
        # Add metadata
        metadata = ItemMetadata(
            value="test_value",
            config={"key1": "value1", "key2": "value2"}
        )
        updated_item = self.client.add_or_update_item_metadata(
            item_name, "test_namespace", metadata
        )
        
        # Verify metadata was added
        self.assertIn("metadata", updated_item)
        self.assertIn("test_namespace", updated_item["metadata"])
        self.assertEqual(updated_item["metadata"]["test_namespace"]["value"], "test_value")
        
        # Clean up
        self.client.delete_item(item_name)
        
    def test_group_item_operations(self):
        """Test group item creation and member management"""
        # Create some test items to add to the group
        item1 = self.create_test_item("Switch1", "Switch")
        item2 = self.create_test_item("Dimmer1", "Dimmer")
        
        # Create a group item
        group_name = f"{self.test_prefix}Group_TestGroup"
        group_item = self.create_test_group_item(
            "TestGroup",
            "Group"
        )
        self.client.add_item_member(group_name, item1["name"])
        group_item = self.client.add_item_member(group_name, item2["name"])
        
        # Verify group was created with members
        self.assertEqual(group_item["name"], group_name)
        self.assertIn("members", group_item)
        self.assertEqual(len(group_item["members"]), 2)
        member_names = [m["name"] for m in group_item["members"]]
        self.assertIn(item1["name"], member_names)
        self.assertIn(item2["name"], member_names)
        
        # Add another member
        item3 = self.create_test_item("String1", "String")
        group_item = self.client.add_item_member(
            group_name,
            item3["name"]
        )
        
        # Verify the member was added
        self.assertEqual(len(group_item["members"]), 3)
        member_names = [m["name"] for m in group_item["members"]]
        self.assertIn(item3["name"], member_names)
        
        # Remove a member
        group_item = self.client.remove_item_member(
            group_name,
            item1["name"]
        )
        
        # Verify the member was removed
        self.assertEqual(len(group_item["members"]), 2)
        member_names = [m["name"] for m in group_item["members"]]
        self.assertNotIn(item1["name"], member_names)
        
        # Clean up
        for item in [item1, item2, item3, group_item]:
            try:
                self.client.delete_item(item["name"])
            except:
                pass
                
    def test_item_state_operations(self):
        """Test updating and reading item states"""
        # Create a test item
        item = self.create_test_item("TestSwitch", "Switch", state="OFF")
        item_name = item["name"]
        
        # Update the state
        self.client.update_item_state(item_name, "ON")
        
        # Verify the state was updated
        updated_item = self.client.get_item(item_name)
        self.assertEqual(updated_item["state"], "ON")
        
        # Test with a number
        dimmer = self.create_test_item("TestDimmer", "Dimmer", state="0")
        self.client.update_item_state(dimmer["name"], "50")
        updated_dimmer = self.client.get_item(dimmer["name"])
        self.assertEqual(updated_dimmer["state"], "50")
        
        # Clean up
        self.client.delete_item(item_name)
        self.client.delete_item(dimmer["name"])

    def test_tag_operations(self):
        """Test creating, listing, and deleting tags"""
        # Test creating a semantic tag
        tag = Tag(
            uid="Location_TestLocation",
            name="TestLocation",
            label="Test Location",
            category="Location",
            description="A test location tag"
        )
        
        # Create tag
        created_tag = self.client.create_semantic_tag(tag)
        self.assertEqual(created_tag["uid"], "Location_TestLocation")
        self.assertEqual(created_tag["name"], "TestLocation")
        self.assertEqual(created_tag["label"], "Test Location")
        
        # Test getting the tag
        retrieved_tag = self.client.get_semantic_tag("Location_TestLocation")
        self.assertIsNotNone(retrieved_tag)
        self.assertEqual(retrieved_tag[0]["uid"], "Location_TestLocation")
        
        # Test listing tags
        tags = self.client.list_semantic_tags()
        self.assertIsInstance(tags, list)
        test_tag = next((t for t in tags if t["uid"] == "Location_TestLocation"), None)
        self.assertIsNotNone(test_tag)
        
        # Test listing tags by category
        location_tags = self.client.list_semantic_tags(category="Location")
        self.assertTrue(any(t["uid"] == "Location_TestLocation" for t in location_tags))
        
        # Clean up
        self.client.delete_semantic_tag("Location_TestLocation")
        
        # Verify tag was deleted
        with self.assertRaises(ValueError):
            self.client.get_semantic_tag("Location_TestLocation")
    
    def test_item_tag_operations(self):
        """Test adding and removing tags from items"""
        # Create a test item
        item = self.create_test_item("TestSwitch", "Switch")
        item_name = item["name"]
        
        # Create a test tag
        tag = Tag(
            uid="Equipment_TestDevice",
            name="TestDevice",
            label="Test Device",
            category="Equipment"
        )
        created_tag = self.client.create_semantic_tag(tag)
        try:
            # Add semantic tag to item
            self.client.add_item_semantic_tag(item_name, created_tag["uid"])
            updated_item = self.client.get_item(item_name)
            self.assertIn("semanticTags", updated_item)
            tag_names = [t["name"] for t in updated_item["semanticTags"]]
            self.assertIn(created_tag["name"], tag_names)
            
            # Add non-semantic tag
            non_semantic_tag = "TestTag"
            updated_item = self.client.add_item_non_semantic_tag(item_name, non_semantic_tag)
            self.assertIn("nonSemanticTags", updated_item)
            self.assertIn(non_semantic_tag, updated_item["nonSemanticTags"])
            
            # Remove semantic tag
            updated_item = self.client.remove_item_semantic_tag(item_name, created_tag["uid"])
            tag_names = [t["name"] for t in updated_item["semanticTags"]]
            self.assertNotIn(created_tag["name"], tag_names)
            
            # Remove non-semantic tag
            updated_item = self.client.remove_item_non_semantic_tag(item_name, non_semantic_tag)
            self.assertNotIn(non_semantic_tag, updated_item["nonSemanticTags"])
            
        finally:
            # Clean up
            self.client.delete_item(item_name)
            self.client.delete_semantic_tag(created_tag["uid"])

    def test_hierarchical_tags(self):
        """Test hierarchical tag operations"""
        # Create parent tag
        parent_tag = Tag(
            uid="Location_TestBuilding",
            name="TestBuilding",
            label="Test Building",
            category="Location"
        )
        created_parent = self.client.create_semantic_tag(parent_tag)
        
        # Create child tag
        child_tag = Tag(
            uid=f"{parent_tag.uid}_TestRoom",
            name="TestRoom",
            label="Test Room",
            category="Location",
            parentuid=parent_tag.uid
        )
        created_child = self.client.create_semantic_tag(child_tag)
        
        try:
            # Test getting child tags
            child_tags = self.client.get_semantic_tag(parent_tag.uid, include_subtags=True)
            self.assertEqual(len(child_tags), 2)  # Should return both parent and child
            
            # Test listing with parent filter
            child_tags = self.client.list_semantic_tags(parent_tag_uid=parent_tag.uid)
            self.assertTrue(any(t["uid"] == child_tag.uid for t in child_tags))
            
        finally:
            # Clean up - must delete child first due to hierarchy
            self.client.delete_semantic_tag(child_tag.uid)
            self.client.delete_semantic_tag(parent_tag.uid)

    def test_create_item_with_all_fields(self):
        """Test creating an item with all possible fields and verify they are set correctly."""
        # Create a group item first to use in group_names
        group_name = f"{self.test_prefix}TestGroup"
        group_item = self.client.create_item(ItemCreate(
            name=group_name,
            type="Group",
            label="Test Group",
            groupType="Dimmer",
            function={"name": "AVG"}  
        ))
        
        # Create an item with all possible fields
        item_name = f"{self.test_prefix}FullItem"
        item = ItemCreate(
            name=item_name,
            type="Dimmer",
            label="Test Full Dimmer Item",
            category="Light",
            groupNames=[group_name],
            semanticTags=["Equipment_Lighting"],
            nonSemanticTags=["TestTag", "Dimmable"],
            metadata={
                "commandDescription": ItemMetadata(value=" ", config={
                    "options": "ON=Switch ON, OFF=Switch OFF, INCREASE=Increase, DECREASE=Decrease"
                }),
                "stateDescription": ItemMetadata(value=" ", config={
                    "minimum": 0,
                    "maximum": 100,
                    "step": 5,
                    "pattern": "%d%%",
                    "readOnly": False,
                    "options": "0=Off, 100=Full"
                }),
                "unit": ItemMetadata(value="%")
            }
        )
        
        # Create the item
        created_item = self.client.create_item(item)
        
        try:
            # Verify the item was created with all fields
            self.assertEqual(created_item["name"], item_name)
            self.assertEqual(created_item["type"], "Dimmer")
            self.assertEqual(created_item["label"], "Test Full Dimmer Item")
            self.assertEqual(created_item["category"], "Light")
            
            # Verify group membership
            self.assertIn(group_name, created_item["groupNames"])
            
            # Get the group to verify its properties
            group = self.client.get_item(group_name)
            self.assertEqual(group["groupType"], "Dimmer")
            self.assertEqual(group["function"]["name"], "AVG")
            
            # Verify tags
            self.assertIn("TestTag", created_item["nonSemanticTags"])
            self.assertIn("Dimmable", created_item["nonSemanticTags"])

            self.assertIn("Equipment_Lighting", created_item["semanticTags"][0]["uid"])
            self.assertIn("Lighting", created_item["semanticTags"][0]["name"])
            self.assertIn("Equipment", created_item["semanticTags"][0]["category"])
            
            # Verify metadata
            self.assertIn("metadata", created_item)
            metadata = created_item["metadata"]
            self.assertIn("commandDescription", metadata)
            self.assertIn("stateDescription", metadata)
            self.assertIn("unit", metadata)
            
            # Verify command options
            command_options = metadata["commandDescription"]["config"]
            self.assertEqual(command_options["options"], "ON=Switch ON, OFF=Switch OFF, INCREASE=Increase, DECREASE=Decrease")
            
            # Verify state description
            state_desc_config = metadata["stateDescription"]["config"]
            self.assertEqual(state_desc_config["minimum"], 0)
            self.assertEqual(state_desc_config["maximum"], 100)
            self.assertEqual(state_desc_config["step"], 5)
            self.assertEqual(state_desc_config["pattern"], "%d%%")
            self.assertFalse(state_desc_config["readOnly"])
            self.assertEqual(state_desc_config["options"], "0=Off, 100=Full")
            
            # Verify unit symbol
            self.assertEqual(metadata["unit"]["value"], "%")
            
        finally:
            # Clean up
            self.client.delete_item(item_name)
            self.client.delete_item(group_name)

    def test_update_item_with_none_or_empty_values(self):
        """Test updating an item with None or empty list values to remove properties"""
        # First create an item with various properties
        item_name = "TestItem_UpdateWithNone"
        group_name = "TestItem_TestGroupForUpdate"
        
        # Create a group first
        self.client.create_item(ItemCreate(
            name=group_name,
            type="Group",
            label="Test Group for Update",
            groupType="Dimmer",
            function={"name": "AVG"}
        ))
        
        # Create initial item with all properties
        item = ItemCreate(
            name=item_name,
            type="Dimmer",
            label="Test Item for Update",
            category="Light",
            groupNames=[group_name],
            semanticTags=["Equipment_Lighting"],
            nonSemanticTags=["TestTag", "Dimmable"],
            metadata={
                "stateDescription": ItemMetadata(value=" ", config={
                    "pattern": "%d%%",
                    "readOnly": False,
                    "options": "0=Off, 100=Full"
                })
            }
        )
        
        # Create the item
        created_item = self.client.create_item(item)
        
        try:
            # Verify the item was created with all fields
            self.assertEqual(created_item["name"], item_name)
            self.assertEqual(created_item["label"], "Test Item for Update")
            self.assertEqual(created_item["category"], "Light")
            self.assertIn(group_name, created_item["groupNames"])
            self.assertIn("TestTag", created_item["nonSemanticTags"])
            self.assertIn("Equipment_Lighting", created_item["semanticTags"][0]["uid"])
            self.assertIn("stateDescription", created_item["metadata"])
            
            # Now update the item with None/empty values to remove properties
            update_data = {
                "name": item_name,
                "label": None,  # None should remove the label
                "category": None,  # None should remove the category
                "nonSemanticTags": [],  # Empty list should remove all non-semantic tags
                "semanticTags": [],  # Empty list should remove all semantic tags
            }
            
            # Update the item
            self.client.remove_item_metadata(item_name, "stateDescription")
            self.client.remove_item_member(group_name, item_name)
            updated_item = self.client.update_item(ItemUpdate(**update_data))
            
            # Verify the updates
            self.assertEqual(updated_item["name"], item_name)
            self.assertNotIn("category", updated_item)  # Category should be removed
            self.assertEqual(updated_item.get("nonSemanticTags", []), [])  # No non-semantic tags
            self.assertEqual(updated_item.get("semanticTags", []), [])  # No semantic tags
            self.assertEqual(updated_item.get("groupNames", []), [])  # No groups
            self.assertNotIn("metadata", updated_item)  # Metadata with semantic namespace should still exist
            self.assertNotIn("label", updated_item)
            
        finally:
            # Clean up
            self.client.delete_item(item_name)
            self.client.delete_item(group_name)

if __name__ == "__main__":
    unittest.main()