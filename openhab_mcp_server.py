#!/usr/bin/env python3
"""
OpenHAB MCP Server - An MCP server that interacts with a real openHAB instance.

This server uses mcp.server for simplified MCP server implementation and
connects to a real openHAB instance via its REST API.
"""

import os
import sys
import requests
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Import the MCP server implementation
from mcp.server import FastMCP
from mcp.server.stdio import stdio_server
from mcp.types import JSONRPCError, INVALID_REQUEST

mcp = FastMCP("OpenHAB MCP Server")

# Load environment variables from .env file
env_file = Path('.env')
if env_file.exists():
    print(f"Loading environment variables from {env_file}", file=sys.stderr)
    load_dotenv(env_file)

# Get OpenHAB connection settings from environment variables
OPENHAB_URL = os.environ.get('OPENHAB_URL', 'http://localhost:8080')
OPENHAB_API_TOKEN = os.environ.get('OPENHAB_API_TOKEN')
OPENHAB_USERNAME = os.environ.get('OPENHAB_USERNAME')
OPENHAB_PASSWORD = os.environ.get('OPENHAB_PASSWORD')

if not OPENHAB_API_TOKEN and not (OPENHAB_USERNAME and OPENHAB_PASSWORD):
    print("Warning: No authentication credentials found in environment variables.", file=sys.stderr)
    print("Set OPENHAB_API_TOKEN or OPENHAB_USERNAME/OPENHAB_PASSWORD in .env file.", file=sys.stderr)

# Pydantic models for payloads
class Item(BaseModel):
    type: str = "String"
    name: str
    state: Optional[str] = None
    label: Optional[str] = None
    tags: List[str] = []
    groupNames: List[str] = []

class ThingStatusInfo(BaseModel):
    status: str
    statusDetail: str = "NONE"
    description: Optional[str] = None

class Thing(BaseModel):
    thingTypeUID: str
    UID: str
    label: Optional[str] = None
    bridgeUID: Optional[str] = None
    configuration: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, str] = Field(default_factory=dict)
    statusInfo: Optional[ThingStatusInfo] = None
    channels: List[Dict[str, Any]] = Field(default_factory=list)

class RuleStatus(BaseModel):
    status: str
    statusDetail: str = "NONE"

class RuleAction(BaseModel):
    id: str
    type: str
    configuration: Dict[str, Any] = Field(default_factory=dict)
    inputs: Dict[str, Any] = Field(default_factory=dict)

class RuleTrigger(BaseModel):
    id: str
    type: str
    configuration: Dict[str, Any] = Field(default_factory=dict)

class RuleCondition(BaseModel):
    id: str
    type: str
    configuration: Dict[str, Any] = Field(default_factory=dict)

class Rule(BaseModel):
    uid: str
    name: str
    description: Optional[str] = None
    status: Optional[RuleStatus] = None
    tags: List[str] = []
    visibility: Optional[str] = None
    editable: bool = True
    configuration: Dict[str, Any] = Field(default_factory=dict)
    configDescriptions: List[Dict[str, Any]] = Field(default_factory=list)
    triggers: List[RuleTrigger] = []
    conditions: List[RuleCondition] = []
    actions: List[RuleAction] = []


# Real openHAB API client
class OpenHABClient:
    """Client for interacting with the openHAB REST API"""
    
    def __init__(self, base_url: str, api_token: Optional[str] = None, 
                 username: Optional[str] = None, password: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        
        # Set up authentication
        if api_token:
            self.session.headers.update({'Authorization': f'Bearer {api_token}'})
        elif username and password:
            self.session.auth = (username, password)
    
    def list_items(self, filter_tag: Optional[str] = None) -> List[Item]:
        """List all items, optionally filtered by tag"""
        if filter_tag:
            response = self.session.get(f"{self.base_url}/rest/items?tags={filter_tag}")
        else:
            response = self.session.get(f"{self.base_url}/rest/items")      
        response.raise_for_status()
        items = [Item(**item) for item in response.json()]
        
        return items
    
    def get_item(self, item_name: str) -> Optional[Item]:
        """Get a specific item by name"""
        if item_name is None:
            return None
        
        try:
            response = self.session.get(f"{self.base_url}/rest/items/{item_name}")
            response.raise_for_status()
            return Item(**response.json())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def create_item(self, item: Item) -> Item:
        """Create a new item"""
        if not item.name:
            raise ValueError("Item must have a name")

        payload = item.dict()
        
        response = self.session.put(
            f"{self.base_url}/rest/items/{item.name}",
            json=payload
        )
        response.raise_for_status()
        
        # Get the created item
        return self.get_item(item.name)
    
    def update_item(self, item_name: str, item: Item) -> Item:
        """Update an existing item"""
        # Get current item to merge with updates
        current_item = self.get_item(item_name)
        if not current_item:
            raise ValueError(f"Item with name '{item_name}' not found")
        
        # Prepare update payload
        payload = {
            "type": item.type or current_item.type,
            "name": item_name,
            "state": item.state or current_item.state,
            "label": item.label or current_item.label,
            "tags": item.tags or current_item.tags,
            "groupNames": item.groupNames or current_item.groupNames
        }
        
        response = self.session.put(
            f"{self.base_url}/rest/items/{item_name}",
            json=payload
        )
        response.raise_for_status()
        
        # Get the updated item
        return self.get_item(item_name)
    
    def delete_item(self, item_name: str) -> bool:
        """Delete an item"""
        response = self.session.delete(f"{self.base_url}/rest/items/{item_name}")
        
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item_name}' not found")
        
        response.raise_for_status()
        return True
    
    def update_item_state(self, item_name: str, state: str) -> Item:
        """Update just the state of an item"""
        # Check if item exists
        if not self.get_item(item_name):
            raise ValueError(f"Item with name '{item_name}' not found")
        
        # Update state
        response = self.session.post(
            f"{self.base_url}/rest/items/{item_name}",
            data=state,
            headers={"Content-Type": "text/plain"}
        )
        response.raise_for_status()
        
        # Get the updated item
        return self.get_item(item_name)
    
    def list_things(self) -> List[Thing]:
        """List all things"""
        response = self.session.get(f"{self.base_url}/rest/things")
        response.raise_for_status()
        return [Thing(**thing) for thing in response.json()]
    
    def get_thing(self, thing_uid: str) -> Optional[Thing]:
        """Get a specific thing by UID"""
        if thing_uid is None:
            return None
        
        try:
            response = self.session.get(f"{self.base_url}/rest/things/{thing_uid}")
            response.raise_for_status()
            return Thing(**response.json())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def list_rules(self, filter_tag: Optional[str] = None) -> List[Rule]:
        """List all rules, optionally filtered by tag"""
        if filter_tag:
            response = self.session.get(f"{self.base_url}/rest/rules?tags={filter_tag}")
        else:
            response = self.session.get(f"{self.base_url}/rest/rules")
        response.raise_for_status()
        return [Rule(**rule) for rule in response.json()]
    
    def get_rule(self, rule_uid: str) -> Optional[Rule]:
        """Get a specific rule by UID"""
        if rule_uid is None:
            return None
        
        try:
            response = self.session.get(f"{self.base_url}/rest/rules/{rule_uid}")
            response.raise_for_status()
            return Rule(**response.json())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def update_rule(self, rule_uid: str, rule_updates: Dict[str, Any]) -> Rule:
        """Update an existing rule with partial updates"""
        # Check if rule exists
        current_rule = self.get_rule(rule_uid)
        if not current_rule:
            raise ValueError(f"Rule with UID '{rule_uid}' not found")
        
        # Get the current rule as a dictionary
        current_rule_dict = current_rule.dict()
        
        # Merge with updates (only updating provided fields)
        for key, value in rule_updates.items():
            if key == "actions" and isinstance(value, list) and len(value) > 0:
                # Handle updating specific actions by ID
                for updated_action in value:
                    if "id" in updated_action:
                        # Find the matching action by ID and update it
                        for i, action in enumerate(current_rule_dict["actions"]):
                            if action["id"] == updated_action["id"]:
                                # Update this specific action
                                current_rule_dict["actions"][i].update(updated_action)
                                break
                        else:
                            # If no matching action found, append it
                            current_rule_dict["actions"].append(updated_action)
                    else:
                        # No ID provided, just append the action
                        current_rule_dict["actions"].append(updated_action)
            else:
                # For other fields, just update directly
                current_rule_dict[key] = value
        
        # Send update request
        response = self.session.put(
            f"{self.base_url}/rest/rules/{rule_uid}",
            json=current_rule_dict
        )
        response.raise_for_status()
        
        # Get the updated rule
        return self.get_rule(rule_uid)
    
    def update_rule_script_action(self, rule_uid: str, action_id: str, script_type: str, script_content: str) -> Rule:
        """Update a script action in a rule"""
        # Prepare the action update
        action_update = {
            "id": action_id,
            "type": "script.ScriptAction",
            "configuration": {
                "type": script_type,  # e.g., "application/javascript"
                "script": script_content
            }
        }
        
        # Update the rule with just this action
        return self.update_rule(rule_uid, {"actions": [action_update]})
    
    def create_rule(self, rule: Rule) -> Rule:
        """Create a new rule"""
        if not rule.uid:
            raise ValueError("Rule must have a UID")
        
        # Prepare payload
        payload = rule.dict()
        
        # Send create request
        response = self.session.post(
            f"{self.base_url}/rest/rules",
            json=payload
        )
        response.raise_for_status()
        
        # Get the created rule
        return self.get_rule(rule.uid)
    
    def delete_rule(self, rule_uid: str) -> bool:
        """Delete a rule"""
        response = self.session.delete(f"{self.base_url}/rest/rules/{rule_uid}")
        
        if response.status_code == 404:
            raise ValueError(f"Rule with UID '{rule_uid}' not found")
        
        response.raise_for_status()
        return True

    def list_scripts(self) -> List[Rule]:
        """List all scripts. A script is a rule without a trigger and tag of 'Script'"""
        return self.list_rules(filter_tag="Script")


    def get_script(self, script_id: str) -> Optional[Rule]:
        """Get a specific script by ID. A script is a rule without a trigger and tag of 'Script'"""
        if script_id is None:
            return None
        
        return self.get_rule(script_id)
    

    def create_script(self, script_id: str, script_type: str, content: str) -> Rule:
        """Create a new script.  A script is a rule without a trigger and tag of 'Script'"""
        if not script_id:
            raise ValueError("Script must have an ID")
        if not content:
            raise ValueError("Script content cannot be empty")
        if not script_type:
            raise ValueError("Script type cannot be empty")
        
        rule = Rule(
            uid=script_id,
            name=script_id,
            tags=["Script"],
            triggers=[],
            actions=[
                {
                    "id": "1",
                    "type": "script.ScriptAction",
                    "configuration": {
                        "type": script_type,  # e.g., "application/javascript"
                        "script": content
                    }
                }
            ]
        )

        return self.create_rule(rule)
    
    def update_script(self, script_id: str, script_type: str, content: str) -> Rule:
        """Update an existing script. A script is a rule without a trigger and tag of 'Script'"""
        rule = self.get_rule(script_id)
        # Check if script exists
        if not rule:
            raise ValueError(f"Script with ID '{script_id}' not found")

        return self.update_rule_script_action(script_id, rule.actions[0].id, script_type, content)
    
    def delete_script(self, script_id: str) -> bool:
        """Delete a script. A script is a rule without a trigger and tag of 'Script'"""
        return self.delete_rule(script_id)  

# Initialize the real OpenHAB client
openhab_client = OpenHABClient(
    base_url=OPENHAB_URL,
    api_token=OPENHAB_API_TOKEN,
    username=OPENHAB_USERNAME,
    password=OPENHAB_PASSWORD
)

@mcp.tool()
def list_items(filter_tag: Optional[str] = None)-> List[Item]:
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
    """List all openHAB scripts. A script is a rule without a trigger and tag of 'Script'"""
    scripts = openhab_client.list_scripts()
    return scripts

@mcp.tool()
def get_script(script_id: str) -> Optional[Rule]:
    """Get a specific openHAB script by ID. A script is a rule without a trigger and tag of 'Script'"""
    script = openhab_client.get_script(script_id)
    return script

@mcp.tool()
def update_rule(rule_uid: str, rule_updates: Dict[str, Any]) -> Rule:
    """Update an existing openHAB rule with partial updates"""
    updated_rule = openhab_client.update_rule(rule_uid, rule_updates)
    return updated_rule

@mcp.tool()
def update_rule_script_action(rule_uid: str, action_id: str, script_type: str, script_content: str) -> Rule:
    """Update a script action in an openHAB rule"""
    updated_rule = openhab_client.update_rule_script_action(rule_uid, action_id, script_type, script_content)
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
    """Create a new openHAB script. A script is a rule without a trigger and tag of 'Script'"""
    created_script = openhab_client.create_script(script_id, script_type, content)
    return created_script

@mcp.tool()
def update_script(script_id: str, script_type: str, content: str) -> Rule:
    """Update an existing openHAB script. A script is a rule without a trigger and tag of 'Script'"""
    updated_script = openhab_client.update_script(script_id, script_type, content)
    return updated_script

@mcp.tool()
def delete_script(script_id: str) -> bool:
    """Delete an openHAB script. A script is a rule without a trigger and tag of 'Script'"""
    return openhab_client.delete_script(script_id)

if __name__ == "__main__":
    mcp.run()
