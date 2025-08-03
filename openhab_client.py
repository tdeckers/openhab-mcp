from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

from models import EnrichedItemChannelLinkDTO, Item, ItemChannelLinkDTO, Rule, Thing


class OpenHABClient:
    """Client for interacting with the openHAB REST API"""

    def __init__(
        self,
        base_url: str,
        api_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

        # Set up authentication
        if api_token:
            self.session.headers.update({"Authorization": f"Bearer {api_token}"})
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
            f"{self.base_url}/rest/items/{item.name}", json=payload
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
            "groupNames": item.groupNames or current_item.groupNames,
        }

        response = self.session.put(
            f"{self.base_url}/rest/items/{item_name}", json=payload
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

    def list_links(
        self, channel_uid: Optional[str] = None, item_name: Optional[str] = None
    ) -> List[EnrichedItemChannelLinkDTO]:
        """List all item-channel links, optionally filtered by channel UID or item name"""
        params = {}
        if channel_uid:
            params["channelUID"] = channel_uid
        if item_name:
            params["itemName"] = item_name

        response = self.session.get(f"{self.base_url}/rest/links", params=params)
        response.raise_for_status()
        return [EnrichedItemChannelLinkDTO(**link) for link in response.json()]

    def get_link(
        self, item_name: str, channel_uid: str
    ) -> Optional[EnrichedItemChannelLinkDTO]:
        """Get a specific item-channel link"""
        if not item_name or not channel_uid:
            return None

        try:
            response = self.session.get(
                f"{self.base_url}/rest/links/{item_name}/{quote(channel_uid, safe='')}"
            )
            response.raise_for_status()
            return EnrichedItemChannelLinkDTO(**response.json())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def create_or_update_link(
        self,
        item_name: str,
        channel_uid: str,
        link_data: Optional[ItemChannelLinkDTO] = None,
    ) -> bool:
        """Create or update an item-channel link"""
        if not item_name or not channel_uid:
            raise ValueError("Item name and channel UID are required")

        # If no link data provided, create minimal link
        if link_data is None:
            payload = {
                "itemName": item_name,
                "channelUID": channel_uid,
            }
        else:
            payload = link_data.dict()

        response = self.session.put(
            f"{self.base_url}/rest/links/{item_name}/{quote(channel_uid, safe='')}",
            json=payload,
        )
        response.raise_for_status()
        return True

    def delete_link(self, item_name: str, channel_uid: str) -> bool:
        """Delete a specific item-channel link"""
        if not item_name or not channel_uid:
            raise ValueError("Item name and channel UID are required")

        response = self.session.delete(
            f"{self.base_url}/rest/links/{item_name}/{quote(channel_uid, safe='')}"
        )

        if response.status_code == 404:
            raise ValueError(
                f"Link between item '{item_name}' and channel '{channel_uid}' not found"
            )

        response.raise_for_status()
        return True

    def get_orphan_links(self) -> List[EnrichedItemChannelLinkDTO]:
        """Get orphaned item-channel links (links to non-existent channels)"""
        response = self.session.get(f"{self.base_url}/rest/links/orphans")
        response.raise_for_status()
        return [EnrichedItemChannelLinkDTO(**link) for link in response.json()]

    def purge_orphan_links(self) -> bool:
        """Remove all orphaned item-channel links"""
        response = self.session.post(f"{self.base_url}/rest/links/purge")
        response.raise_for_status()
        return True

    def delete_all_links_for_object(self, object_name: str) -> bool:
        """Delete all links for a specific item or thing"""
        if not object_name:
            raise ValueError("Object name (item name or thing UID) is required")

        response = self.session.delete(f"{self.base_url}/rest/links/{object_name}")
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
            headers={"Content-Type": "text/plain"},
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
            f"{self.base_url}/rest/rules/{rule_uid}", json=current_rule_dict
        )
        response.raise_for_status()

        # Get the updated rule
        return self.get_rule(rule_uid)

    def update_rule_script_action(
        self, rule_uid: str, action_id: str, script_type: str, script_content: str
    ) -> Rule:
        """Update a script action in a rule"""
        # Prepare the action update
        action_update = {
            "id": action_id,
            "type": "script.ScriptAction",
            "configuration": {
                "type": script_type,  # e.g., "application/javascript"
                "script": script_content,
            },
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
        response = self.session.post(f"{self.base_url}/rest/rules", json=payload)
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
                        "script": content,
                    },
                }
            ],
        )

        return self.create_rule(rule)

    def update_script(self, script_id: str, script_type: str, content: str) -> Rule:
        """Update an existing script. A script is a rule without a trigger and tag of 'Script'"""
        rule = self.get_rule(script_id)
        # Check if script exists
        if not rule:
            raise ValueError(f"Script with ID '{script_id}' not found")

        return self.update_rule_script_action(
            script_id, rule.actions[0].id, script_type, content
        )

    def delete_script(self, script_id: str) -> bool:
        """Delete a script. A script is a rule without a trigger and tag of 'Script'"""
        return self.delete_rule(script_id)

    def run_rule_now(self, rule_uid: str) -> bool:
        """Run a rule immediately"""
        if not rule_uid:
            raise ValueError("Rule UID cannot be empty")

        # Check if rule exists
        if not self.get_rule(rule_uid):
            raise ValueError(f"Rule with UID '{rule_uid}' not found")

        # Send request to run the rule
        response = self.session.post(f"{self.base_url}/rest/rules/{rule_uid}/runnow")

        if response.status_code == 404:
            raise ValueError(f"Rule with UID '{rule_uid}' not found")

        response.raise_for_status()
        return True
