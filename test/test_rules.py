import unittest
import time
from typing import Dict, Any, List
from openhab_client import OpenHABClient
from models import RuleCreate, RuleUpdate, RuleAction, RuleTrigger, RuleCondition

class TestOpenHABRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize the OpenHAB client before running tests"""
        cls.client = OpenHABClient(
            base_url="https://openhab.amfthome.org",  # Update with your OpenHAB URL
            api_token="oh.admintoken.CJpWSex2w3OSDOCUyPYy5qt9YbqoJkB4G4AggnAub1TUiIKEWyV2MsRoJGmE3DRlvzJojwp9pyKQ622Yig"  # Update with your API token or use username/password
        )
        # Prefix for test rules to easily identify and clean them up
        cls.test_prefix = "TestRule_"
        
    def setUp(self):
        """Run before each test method"""
        # Ensure we start with a clean state
        self.cleanup_test_rules()
        
    def tearDown(self):
        """Run after each test method"""
        self.cleanup_test_rules()
        
    def cleanup_test_rules(self):
        """Clean up all test rules"""
        try:
            rules = self.client.list_rules().get("rules", [])
            for rule in rules:
                if rule["name"] and rule["name"].startswith(self.test_prefix):
                    self.client.delete_rule(rule["uid"])
        except Exception as e:
            print(f"Warning: Failed to clean up test rules: {e}")

    def create_test_rule(self, name_suffix: str, **kwargs) -> Dict[str, Any]:
        """Helper method to create a test rule"""
        rule_name = f"{self.test_prefix}{name_suffix}"
        rule = RuleCreate(
            uid=f"test_rule_{name_suffix.lower()}",
            name=rule_name,
            description=f"Test rule {name_suffix}",
            tags=["TestTag"],
            triggers=[{
                "id": "1",
                "type": "core.ItemStateChangeTrigger",
                "configuration": {
                    "itemName": "Test_Item",
                    "state": "ON"
                }
            }],
            actions=[{
                "id": "2",
                "type": "script.ScriptAction",
                "configuration": {
                    "type": "text/plain",
                    "script": "print('Test rule executed')"
                }
            }]
        )
        return self.client.create_rule(rule)
        
    def test_create_and_delete_rule(self):
        """Test creating and deleting a rule"""
        # Create a test rule
        rule = self.create_test_rule("BasicRule")
        self.assertEqual(rule["name"], f"{self.test_prefix}BasicRule")
        self.assertEqual(rule["description"], "Test rule BasicRule")
        
        # Verify the rule exists
        rules = self.client.list_rules(filter_tag="TestTag").get("rules", [])
        rule_names = [r["name"] for r in rules]
        self.assertIn(f"{self.test_prefix}BasicRule", rule_names)
        
        # Delete the rule
        result = self.client.delete_rule(rule["uid"])
        self.assertTrue(result)
        
        # Verify the rule was deleted
        rules = self.client.list_rules(filter_tag="TestTag").get("rules", [])
        rule_names = [r["name"] for r in rules]
        self.assertNotIn(f"{self.test_prefix}BasicRule", rule_names)
        
    def test_get_rule(self):
        """Test retrieving a specific rule"""
        # Create a test rule
        created_rule = self.create_test_rule("GetRuleTest")
        rule_uid = created_rule["uid"]
        
        # Get the rule
        retrieved_rule = self.client.get_rule(rule_uid)
        self.assertEqual(retrieved_rule["uid"], rule_uid)
        self.assertEqual(retrieved_rule["name"], f"{self.test_prefix}GetRuleTest")
        
        # Clean up
        self.client.delete_rule(rule_uid)
        
    def test_update_rule(self):
        """Test updating a rule"""
        # Create a test rule
        created_rule = self.create_test_rule("UpdateRuleTest")
        rule_uid = created_rule["uid"]
        
        # Update the rule
        update_data = RuleUpdate(
            uid=rule_uid,
            description="Updated description",
            tags=["TestTag", "UpdatedTag"]
        )
        updated_rule = self.client.update_rule(update_data)
        
        # Verify the update
        self.assertEqual(updated_rule["description"], "Updated description")
        self.assertIn("UpdatedTag", updated_rule["tags"])
        
        # Clean up
        self.client.delete_rule(rule_uid)
        
    def test_run_rule(self):
        """Test running a rule manually"""
        # Create a test rule with a simple action
        rule_name = f"{self.test_prefix}RunRuleTest"
        rule = RuleCreate(
            uid="test_run_rule",
            name=rule_name,
            description="Test rule for running manually",
            tags=["TestTag"],
            triggers=[{
                "id": "1",
                "type": "core.ItemStateChangeTrigger",
                "configuration": {
                    "itemName": "Test_Item",
                    "state": "ON"
                }
            }],
            actions=[{
                "id": "2",
                "type": "script.ScriptAction",
                "configuration": {
                    "type": "text/plain",
                    "script": "print('Rule executed at ' + new Date().toISOString())"
                }
            }]
        )
        created_rule = self.client.create_rule(rule)
        
        # Run the rule manually
        result = self.client.run_rule_now(created_rule["uid"])
        self.assertTrue(result)
        
        # Clean up
        self.client.delete_rule(created_rule["uid"])
        
    def test_enable_disable_rule(self):
        """Test enabling and disabling a rule"""
        # Create a test rule
        created_rule = self.create_test_rule("EnableDisableTest")
        rule_uid = created_rule["uid"]
        
        # Disable the rule
        result = self.client.set_rule_enabled(rule_uid, False)
        self.assertTrue(result)
        
        # Verify the rule is disabled
        rule = self.client.get_rule(rule_uid)
        self.assertEqual(rule.get("status", {}).get("status"), "UNINITIALIZED")
        
        # Enable the rule
        result = self.client.set_rule_enabled(rule_uid, True)
        self.assertTrue(result)
        
        # Verify the rule is enabled
        rule = self.client.get_rule(rule_uid)
        self.assertEqual(rule.get("status", {}).get("status"), "IDLE")
        
        # Clean up
        self.client.delete_rule(rule_uid)
        
    def test_script_operations(self):
        """Test script-specific operations"""
        # Create a script
        script_id = "test_script"
        script_name = f"{self.test_prefix}TestScript"
        script_type = "application/javascript"
        script_content = "console.log('Hello from test script');"
        
        # Create the script
        created_script = self.client.create_script(
            script_id=script_id,
            script_name=script_name,
            script_type=script_type,
            content=script_content
        )
        
        # Verify the script was created
        self.assertEqual(created_script["uid"], script_id)
        self.assertEqual(created_script["name"], script_name)
        self.assertIn("Script", created_script.get("tags", []))
        
        # Get the script
        retrieved_script = self.client.get_script(script_id)
        self.assertEqual(retrieved_script["uid"], script_id)
        
        # Update the script
        updated_content = "console.log('Updated script content');"
        updated_script = self.client.update_script(
            script_id=script_id,
            script_name=script_name,
            script_type=script_type,
            content=updated_content
        )
        
        # Verify the update
        self.assertEqual(len(updated_script["actions"]), 1)
        self.assertEqual(updated_script["actions"][0]["configuration"]["script"], updated_content)
        
        # Clean up
        self.client.delete_script(script_id)

def test_comprehensive_rule_updates(self):
    """Test comprehensive rule updates including script action modifications"""
    # Create a base rule with a single action
    rule_name = f"{self.test_prefix}ComprehensiveUpdateTest"
    rule = RuleCreate(
        uid="test_comprehensive_update",
        name=rule_name,
        description="Test rule for comprehensive updates",
        tags=["TestTag"],
        triggers=[{
            "id": "trigger1",
            "type": "core.ItemStateChangeTrigger",
            "configuration": {
                "itemName": "Test_Item",
                "state": "ON"
            }
        }],
        actions=[{
            "id": "action1",
            "type": "script.ScriptAction",
            "configuration": {
                "type": "text/plain",
                "script": "console.log('Initial action');"
            }
        }]
    )
    
    # Create the initial rule
    created_rule = self.client.create_rule(rule)
    rule_uid = created_rule["uid"]
    
    # --- Test 1: Add a new action ---
    update_data = RuleUpdate(
        uid=rule_uid,
        actions=[
            {
                "id": "action1",  # Keep existing action
                "type": "script.ScriptAction",
                "configuration": {
                    "type": "text/plain",
                    "script": "console.log('Initial action');"
                }
            },
            {  # Add new action
                "id": "action2",
                "type": "script.ScriptAction",
                "configuration": {
                    "type": "application/javascript",
                    "script": "items.getItem('Test_Item').sendCommand('OFF');"
                }
            }
        ]
    )
    
    updated_rule = self.client.update_rule(update_data)
    self.assertEqual(len(updated_rule["actions"]), 2)
    
    # Verify both actions exist
    action_ids = [a["id"] for a in updated_rule["actions"]]
    self.assertIn("action1", action_ids)
    self.assertIn("action2", action_ids)
    
    # --- Test 2: Update an existing action ---
    update_data = RuleUpdate(
        uid=rule_uid,
        actions=[
            {
                "id": "action1",
                "type": "script.ScriptAction",
                "configuration": {
                    "type": "text/plain",
                    "script": "console.log('Updated initial action');"  # Updated script
                }
            },
            {
                "id": "action2",  # Keep as is
                "type": "script.ScriptAction",
                "configuration": {
                    "type": "application/javascript",
                    "script": "items.getItem('Test_Item').sendCommand('OFF');"
                }
            }
        ]
    )
    
    updated_rule = self.client.update_rule(update_data)
    action1 = next(a for a in updated_rule["actions"] if a["id"] == "action1")
    self.assertIn("Updated initial action", action1["configuration"]["script"])
    
    # --- Test 3: Remove an action and add a new one ---
    update_data = RuleUpdate(
        uid=rule_uid,
        actions=[
            {  # Keep action1, remove action2, add action3
                "id": "action1",
                "type": "script.ScriptAction",
                "configuration": {
                    "type": "text/plain",
                    "script": "console.log('Updated initial action');"
                }
            },
            {  # New action
                "id": "action3",
                "type": "script.ScriptAction",
                "configuration": {
                    "type": "application/javascript",
                    "script": "console.log('Third action added');"
                }
            }
        ]
    )
    
    updated_rule = self.client.update_rule(update_data)
    self.assertEqual(len(updated_rule["actions"]), 2)
    
    # Verify the correct actions are present
    action_ids = [a["id"] for a in updated_rule["actions"]]
    self.assertIn("action1", action_ids)
    self.assertIn("action3", action_ids)
    self.assertNotIn("action2", action_ids)
    
    # --- Test 4: Update multiple aspects of the rule ---
    update_data = RuleUpdate(
        uid=rule_uid,
        description="Fully updated rule",
        tags=["TestTag", "UpdatedTag", "FinalTag"],
        configuration={
            "customConfig": "value123",
            "anotherConfig": 42
        },
        actions=[
            {
                "id": "action1",
                "type": "script.ScriptAction",
                "configuration": {
                    "type": "text/plain",
                    "script": "console.log('Final update to action1');"
                }
            },
            {
                "id": "action4",  # New action replacing action3
                "type": "script.ScriptAction",
                "configuration": {
                    "type": "application/javascript",
                    "script": "console.log('Fourth action with different content');"
                }
            }
        ]
    )
    
    updated_rule = self.client.update_rule(update_data)
    
    # Verify all updates were applied
    self.assertEqual(updated_rule["description"], "Fully updated rule")
    self.assertEqual(set(updated_rule["tags"]), {"TestTag", "UpdatedTag", "FinalTag"})
    self.assertEqual(updated_rule["configuration"].get("customConfig"), "value123")
    self.assertEqual(updated_rule["configuration"].get("anotherConfig"), 42)
    
    # Verify actions
    self.assertEqual(len(updated_rule["actions"]), 2)
    action_ids = [a["id"] for a in updated_rule["actions"]]
    self.assertIn("action1", action_ids)
    self.assertIn("action4", action_ids)
    
    # Verify action1 was updated
    action1 = next(a for a in updated_rule["actions"] if a["id"] == "action1")
    self.assertIn("Final update to action1", action1["configuration"]["script"])
    
    # Clean up
    self.client.delete_rule(rule_uid)

if __name__ == "__main__":
    unittest.main()