import re
import requests
import random
import string
from typing import Dict, List, Optional, Any, Set
from pydantic import create_model
import json

from models import (
    Item,
    CreateItem,
    ItemMetadata,
    Link,
    Thing,
    Tag,
    RuleDetails,
    ItemPersistence,
)


DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


class OpenHABClient:
    """Client for interacting with the openHAB REST API"""

    def __init__(
        self,
        base_url: str,
        api_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        generate_uids: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

        # Set up authentication
        if api_token:
            self.session.headers.update({"X-OPENHAB-TOKEN": api_token})
        elif username and password:
            self.session.auth = (username, password)

    def generate_uid(self) -> str:
        return "".join(
            random.SystemRandom().choice(string.ascii_lowercase + string.digits)
            for _ in range(10)
        )

    def _filter_item_fields(self, item: Dict[str, Any], output_fields: Optional[Set[str]]) -> Dict[str, Any]:
        """Filter item fields based on the requested output fields."""
        if output_fields is None:
            return item
            
        filtered_item = {}
        # Always include name for identification
        if "name" in item:
            filtered_item["name"] = item["name"]
            
        # Include all requested fields that exist in the item
        for field in output_fields:
            if field in item:
                filtered_item[field] = item[field]
            
        return filtered_item

    def _process_member(self, member: Dict[str, Any], output_fields: Optional[Set[str]], tags: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process a single member item and its nested members with field filtering."""
        # Process tags if needed
        member_tags = member.get("tags", []).copy()
        
        if not output_fields or (member_tags and output_fields and ("semantic_tags" in output_fields or "non_semantic_tags" in output_fields)):
            semantic_tags = [tag for tag in tags if tag.get('name') in member_tags]
            non_semantic_tags = [tag for tag in member_tags if tag not in [t.get('name', '') for t in tags]]
            
            if output_fields is None:
                member["semantic_tags"] = semantic_tags
                member["non_semantic_tags"] = non_semantic_tags
            else:
                if "semantic_tags" in output_fields:
                    member["semantic_tags"] = semantic_tags
                if "non_semantic_tags" in output_fields:
                    member["non_semantic_tags"] = non_semantic_tags
        
        # Rest of the method remains the same
        if "tags" in member:
            del member["tags"]
            
        # Filter member fields
        filtered_member = self._filter_item_fields(member, output_fields)
        
        # Process nested members if they exist and members are requested
        if "members" in member and (not output_fields or "members" in output_fields):
            filtered_members = []
            for nested_member in member["members"]:
                filtered_nested = self._process_member(nested_member, output_fields, tags)
                filtered_members.append(filtered_nested)
            filtered_member["members"] = filtered_members
            
        return filtered_member

    def list_items(
        self,
        page: int = 1,
        page_size: int = 15,
        sort_order: str = "asc",
        filter_tag: Optional[str] = None,
        filter_type: Optional[str] = None,
        filter_name: Optional[str] = None,
        filter_fields: List[str] = [],
    ) -> Dict[str, Any]:
        """
        List items with pagination

        Args:
            page: 1-based page number
            page_size: Number of items per page
            sort_order: Sort order ("asc" or "desc")
            filter_tag: Optional filter items by tag name or tag UID
            filter_type: Optional filter items by type
            filter_name: Optional filter items by name
            filter_fields: Optional filter items by fields

        Returns:
            Dictionary containing the paginated results and pagination info
        """
        # Get all tags for semantic/non-semantic tag processing
        tags = self.list_tags()

        if filter_tag and "_" in filter_tag:
            filter_tag = filter_tag.split("_")[-1]

        # Prepare API parameters
        params = {}
        if filter_tag:
            params["tags"] = filter_tag
        if filter_type:
            params["type"] = filter_type
        
        # Determine which fields to include in the final output
        output_fields = set(filter_fields) if filter_fields else None
        
        if output_fields:
            # Prepare API fields to request
            api_fields = {"name"}  # Always include name for identification
            
            # Add fields needed for tag processing
            if ("semantic_tags" in output_fields or "non_semantic_tags" in output_fields):
                api_fields.update(["tags"])
                
            # Add other requested fields
            if output_fields:
                api_fields.update(f for f in output_fields if f not in ["semantic_tags", "non_semantic_tags"])
                
            # Convert to comma-separated string for the API
            params["fields"] = ",".join(api_fields)

        # Set recursive if members are requested
        if not filter_fields or "members" in filter_fields:
            params["recursive"] = "true"
            
        # Make the API request
        response = self.session.get(f"{self.base_url}/rest/items", params=params)
        response.raise_for_status()

        # Process the response
        response_json = response.json()
        processed_items = []
        
        for item in response_json:
            # Skip items that don't match the name filter (if provided)
            if filter_name and filter_name.lower() not in item.get("name", "").lower():
                continue
                
            # Process the item and its members
            processed_item = self._process_member(item, output_fields, tags)
            processed_items.append(processed_item)
        
        # Apply sorting
        reverse_sort = sort_order.lower() == "desc"
        processed_items.sort(key=lambda x: x.get("name", ""), reverse=reverse_sort)
        
        # Apply pagination
        total_items = len(processed_items)
        total_pages = (total_items + page_size - 1) // page_size if page_size > 0 else 1
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_items = processed_items[start_idx:end_idx]
        
        # Return paginated results as a dictionary
        return {
            "items": paginated_items,
            "pagination": {
                "total_elements": total_items,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1
            }
        }

    def create_item(self, item: CreateItem) -> Dict[str, Any]:
        """Create a new item"""

        item.raise_for_errors()

        payload = item.model_dump()
        
        # Handle tags
        payload["tags"] = []
        if "semantic_tags" in payload:
            payload["tags"] += [tag.name for tag in payload["semantic_tags"]]
            del payload["semantic_tags"]
        if "non_semantic_tags" in payload:
            payload["tags"] += payload["non_semantic_tags"]
            del payload["non_semantic_tags"]
        
        # Remove None values and empty lists from payload
        payload = {
            k: v for k, v in payload.items() 
            if v is not None and not (isinstance(v, (list, dict)) and not v)
        }

        response = self.session.put(
            f"{self.base_url}/rest/items/{item.name}", json=payload
        )
        response.raise_for_status()

        # Get the created item
        return next(
            iter(
                item
                for item in self.list_items(filter_name=item.name, page_size=1)["items"]
            ),
            None,
        )

    def create_item_metadata(
        self, item_name: str, namespace: str, metadata: ItemMetadata
    ) -> Dict[str, Any]:
        """
        Create new metadata for a specific openHAB item.

        Args:
            item_name: Name of the item to create metadata for
            namespace: Namespace for the metadata (must be unique per item)
            metadata: ItemMetadata object containing the metadata value and config

        Returns:
            Dict[str, Any]: A dictionary containing the updated item data

        Raises:
            ValueError: If the metadata is invalid or the namespace already exists
            requests.HTTPError: If the API request fails
            KeyError: If the specified item doesn't exist
        """

        # Get the item using list_items with name filter
        result = self.list_items(filter_name=item_name, page_size=1)
        if not result["items"]:
            raise KeyError(f"Item with name '{item_name}' not found")
        item = next(
            iter(
                item
                for item in self.list_items(filter_name=item_name, page_size=1)["items"]
            ),
            None,
        )

        if "metadata" in item and namespace in item["metadata"]:
            raise ValueError(
                f"Namespace '{namespace}' already exists for item '{item_name}'"
            )

        payload = {
            "value": metadata.value,
            "config": metadata.config,
        }

        response = self.session.put(
            f"{self.base_url}/rest/items/{item_name}/metadata/{namespace}", json=payload
        )
        response.raise_for_status()

        # Get the updated item using list_items with name filter
        return next(
            iter(
                item
                for item in self.list_items(filter_name=item_name, page_size=1)["items"]
            ),
            None,
        )

    def update_item_metadata(
        self, item_name: str, namespace: str, metadata: ItemMetadata
    ) -> Dict[str, Any]:
        """Update metadata for a specific item"""
        # Get the item using list_items with name filter
        result = self.list_items(filter_name=item_name, page_size=1)
        if not result["items"]:
            raise KeyError(f"Item with name '{item_name}' not found")
        item = next(
            (
                item
                for item in self.list_items(filter_name=item_name, page_size=1)["items"]
            ),
            None,
        )

        if "metadata" in item and namespace not in item["metadata"]:
            raise ValueError(
                f"Namespace '{namespace}' does not exist for item '{item_name}'"
            )

        payload = {
            "value": metadata.value,
            "config": metadata.config,
        }

        response = self.session.put(
            f"{self.base_url}/rest/items/{item_name}/metadata/{namespace}", json=payload
        )
        response.raise_for_status()

        # Get the updated item using list_items with name filter
        return next(
            iter(
                item
                for item in self.list_items(filter_name=item_name, page_size=1)["items"]
            ),
            None,
        )
    
    def delete_item_metadata(self, item_name: str, namespace: str) -> bool:
        """Delete metadata for a specific item"""
        # Get the item using list_items with name filter
        result = self.list_items(filter_name=item_name, page_size=1)
        if not result["items"]:
            raise KeyError(f"Item with name '{item_name}' not found")
        item = next(
            (
                item
                for item in self.list_items(filter_name=item_name, page_size=1)["items"]
            ),
            None,
        )

        if "metadata" in item and namespace not in item["metadata"]:
            raise KeyError(
                f"Namespace '{namespace}' does not exist for item '{item_name}'"
            )

        response = self.session.delete(
            f"{self.base_url}/rest/items/{item_name}/metadata/{namespace}"
        )
        response.raise_for_status()

        # Get the updated item using list_items with name filter
        return next(
            iter(
                item
                for item in self.list_items(filter_name=item_name, page_size=1)["items"]
            ),
            None,
        )
    
    def delete_item_semantic_tag(self, item_name: str, tag_uid: str) -> bool:
        """Delete semantic tag for a specific item"""
        # Get the item using list_items with name filter
        result = self.list_items(filter_name=item_name, page_size=1)
        if not result["items"]:
            raise KeyError(f"Item with name'{item_name}' not found")
        item = next(
            (
                item
                for item in self.list_items(filter_name=item_name, page_size=1)["items"]
            ),
            None,
        )

        tag = self.get_tag(tag_uid, include_subtags=False)[0]
        if not tag:
            raise KeyError(f"Tag '{tag_uid}' not found")
        
        if tag["name"] not in [tag["name"] for tag in item["semantic_tags"]]:
            raise KeyError(f"Tag '{tag_uid}' does not exist for item '{item_name}'")

        response = self.session.delete(
            f"{self.base_url}/rest/items/{item_name}/tags/{tag['name']}"
        )
        response.raise_for_status()

        # Get the updated item using list_items with name filter
        return next(
            iter(
                item
                for item in self.list_items(filter_name=item_name, page_size=1)["items"]
            ),
            None,
        )
    
    def delete_item_non_semantic_tag(self, item_name: str, tag_name: str) -> bool:
        """Delete non-semantic tag for a specific item"""
        # Get the item using list_items with name filter
        result = self.list_items(filter_name=item_name, page_size=1)
        if not result["items"]:
            raise KeyError(f"Item with name'{item_name}' not found")
        item = next(
            (
                item
                for item in self.list_items(filter_name=item_name, page_size=1)["items"]
            ),
            None,
        )

        if tag_name not in item["non_semantic_tags"]:
            raise KeyError(f"Tag '{tag_name}' does not exist for item '{item_name}'")

        response = self.session.delete(
            f"{self.base_url}/rest/items/{item_name}/tags/{tag_name}"
        )
        response.raise_for_status()

        # Get the updated item using list_items with name filter
        return next(
            iter(
                item
                for item in self.list_items(filter_name=item_name, page_size=1)["items"]
            ),
            None,
        )

    def update_item(self, item: Item) -> Dict[str, Any]:
        """Update an existing item"""
        # Validate the item before processing
        try:
            item.raise_for_errors()
    

            # Get current item to merge with updates using list_items with name filter
            result = self.list_items(filter_name=item.name, page_size=1)
            if not result["items"]:
                raise KeyError(f"Item with name '{item.name}' not found")
            current_item = next(
                iter(
                    item
                    for item in self.list_items(filter_name=item.name, page_size=1)["items"]
                ),
                None,
            )

            tags = []
            if hasattr(item, 'semantic_tags') and item.semantic_tags:
                tags += [tag.name for tag in item.semantic_tags]
            if hasattr(item, 'non_semantic_tags') and item.non_semantic_tags:
                tags += item.non_semantic_tags
                
            # Get the tags from the current item
            current_tags = []
            if current_item["semantic_tags"]:
                current_tags += [tag["name"] for tag in current_item["semantic_tags"]]
            if current_item["non_semantic_tags"]:
                current_tags += current_item["non_semantic_tags"]

            # Build payload with only non-None values from item or current_item
            payload = {
                "type": item.type or current_item.get("type"),
                "name": item.name,
            }
            
            # Add optional fields only if they have a value in either item or current_item
            if item.label is not None or current_item.get("label"):
                payload["label"] = item.label if item.label is not None else current_item.get("label")
                
            if item.category is not None or current_item.get("category"):
                payload["category"] = item.category if item.category is not None else current_item.get("category")
                
            if tags or current_tags:
                payload["tags"] = tags if tags else current_tags
                
            if item.groupNames is not None or current_item.get("groupNames"):
                payload["groupNames"] = item.groupNames if item.groupNames is not None else current_item.get("groupNames")
                
            if item.groupType is not None or current_item.get("groupType"):
                payload["groupType"] = item.groupType if item.groupType is not None else current_item.get("groupType")
                
            if item.function is not None or current_item.get("function"):
                payload["function"] = item.function if item.function is not None else current_item.get("function")
                
            if item.members is not None or current_item.get("members"):
                members = [member.model_dump() for member in (item.members if item.members is not None else [])] if item.members is not None else current_item.get("members")
                if members is not None:  # Only add if not None
                    payload["members"] = members
                    
            if item.commandDescription is not None or current_item.get("commandDescription"):
                command_desc = item.commandDescription.model_dump() if item.commandDescription is not None else current_item.get("commandDescription")
                if command_desc is not None:  # Only add if not None
                    payload["commandDescription"] = command_desc
                    
            if item.stateDescription is not None or current_item.get("stateDescription"):
                state_desc = item.stateDescription.model_dump() if item.stateDescription is not None else current_item.get("stateDescription")
                if state_desc is not None:  # Only add if not None
                    payload["stateDescription"] = state_desc
                    
            if item.unitSymbol is not None or current_item.get("unitSymbol"):
                payload["unitSymbol"] = item.unitSymbol if item.unitSymbol is not None else current_item.get("unitSymbol")

            print(json.dumps(payload, indent=2))  # Pretty print for debugging
            response = self.session.put(
                f"{self.base_url}/rest/items/{item.name}",
                json=payload  # Let requests handle the JSON serialization
            )
            response.raise_for_status()

            # Get the updated item using list_items with name filter
            result = self.list_items(filter_name=item.name, page_size=1)
            return result["items"][0]
        except ValueError as e:
            raise ValueError(f"Item validation failed: {e}")

    def update_item_state(self, item_name: str, state: str) -> Dict[str, Any]:
        """Update just the state of an item"""
        # Check if item exists using list_items with name filter
        if not next(
            iter(
                item
                for item in self.list_items(filter_name=item_name, page_size=1)["items"]
            ),
            None,
        ):
            raise KeyError(f"Item with name '{item_name}' not found")

        # Update state
        response = self.session.post(
            f"{self.base_url}/rest/items/{item_name}",
            data=state,
            headers={"Content-Type": "text/plain"},
        )
        response.raise_for_status()

        # Get the updated item using list_items with name filter
        return next(
            iter(
                item
                for item in self.list_items(filter_name=item_name, page_size=1)["items"]
            ),
            None,
        )
 
    def list_things(
        self,
        page: int = 1,
        page_size: int = 50,
        sort_order: str = "asc",
    ) -> Dict[str, Any]:
        """
        List things with pagination

        Args:
            page: 1-based page number
            page_size: Number of items per page (default: 50)
            sort_order: Sort by UID in ascending or descending order ("asc" or "desc")

        Returns:
            PaginatedThings object containing the paginated results and pagination info
        """
        # Get all things
        response = self.session.get(f"{self.base_url}/rest/things")
        response.raise_for_status()

        # Convert to Thing objects
        things = json.loads(response.text)
        for thing in things:
            thing.pop('channels', None)

        # Sort the things
        reverse_sort = sort_order.lower() == "desc"
        things.sort(
            key=lambda x: str(x["UID"]).lower() if x["UID"] else "", reverse=reverse_sort
        )

        # Calculate pagination
        total_elements = len(things)
        total_pages = (
            (total_elements + page_size - 1) // page_size if page_size > 0 else 1
        )
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        # Get the page of items
        paginated_items = things[start_idx:end_idx]

        return {
            "things": paginated_items,
            "pagination": {
                "total_elements": total_elements,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": end_idx < total_elements,
                "has_previous": start_idx > 0,
            },
        }

    def get_thing_channels(self, thing_uid: str, linked_only: bool = False) -> Optional[List[Dict[str, Any]]]:
        """Get the channels of a specific thing by UID
        
        Args:
            thing_uid: The UID of the thing
            linked_only: If True, only return channels with linked items
                        If False, return all channels (default)
                        
        Returns:
            List of channel dictionaries, or None if thing not found
        """
        if thing_uid is None:
            return None

        try:
            response = self.session.get(f"{self.base_url}/rest/things/{thing_uid}")
            response.raise_for_status()
            channels = json.loads(response.text).get("channels", [])
            
            if linked_only:
                return [channel for channel in channels if channel.get("linkedItems")]
            
            return channels
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def create_thing(self, thing: Thing) -> Dict[str, Any]:
        """Create a new thing"""

        if not thing.thingTypeUID:
            raise ValueError("Thing must have a thingTypeUID")

        if not thing.UID:
            if self.generate_uids:
                thing.UID = (
                    thing.thingTypeUID
                    + ":"
                    + (
                        (thing.bridgeUID + ":" + self.generate_uid())
                        if thing.bridgeUID
                        else self.generate_uid()
                    )
                )
            else:
                raise ValueError("Thing must have a UID")

        if thing.bridgeUID:
            pattern = r"{0}:{1}:(.+)".format(thing.thingTypeUID, thing.bridgeUID)
        else:
            pattern = r"{0}:(.+)".format(thing.thingTypeUID)
        result = re.search(pattern, thing.UID)
        if not result:
            raise ValueError(
                "Thing UID must be in format 'binding_id:thing_type_id' or 'binding_id:thing_type_id:bridge_id:thing_id'"
            )

        payload = thing.model_dump()
        payload.update({"ID": result.groups()[-1]})

        response = self.session.post(f"{self.base_url}/rest/things", json=payload)
        response.raise_for_status()

        # Get the created thing
        return next(
            iter(
                thing
                for thing in self.list_things(filter_uid=thing.UID, page_size=1)["things"]
            ),
            None,
        )

    def update_thing(self, thing: Thing) -> Dict[str, Any]:
        """Update an existing thing"""
        # Get current thing to merge with updates
        current_thing = next(
            iter(
                thing
                for thing in self.list_things(filter_uid=thing.UID, page_size=1)["things"]
            ),
            None,
        )
        if not current_thing:
            raise ValueError(f"Thing with UID '{thing.UID}' not found")

        # Prepare update payload
        payload = {
            "thingTypeUID": thing.thingTypeUID,
            "UID": thing.UID,
            "label": thing.label or current_thing["label"],
            "configuration": thing.configuration or current_thing["configuration"],
            "properties": thing.properties or current_thing["properties"],
            "channels": thing.channels or current_thing["channels"],
        }

        response = self.session.put(
            f"{self.base_url}/rest/things/{thing.UID}", json=payload
        )
        response.raise_for_status()

        # Get the updated thing
        return next(
            iter(
                thing
                for thing in self.list_things(filter_uid=thing.UID, page_size=1)["things"]
            ),
            None,
        )

    def delete_thing(self, thing_uid: str) -> bool:
        """Delete a thing"""
        response = self.session.delete(f"{self.base_url}/rest/things/{thing_uid}")

        if response.status_code == 404:
            raise KeyError(f"Thing with UID '{thing_uid}' not found")

        response.raise_for_status()
        return True

    def list_rules(
        self,
        page: int = 1,
        page_size: int = 15,
        sort_order: str = "asc",
        filter_tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List all rules, optionally filtered by tag

        Args:
            page: 1-based page number (default: 1)
            page_size: Number of elements per page (default: 15)
            sort_order: Sort order ("asc" or "desc") (default: "asc")
            filter_tag: Tag to filter rules by (default: None)
        """
        # Prepare query parameters
        params = {}
        if filter_tag:
            params["tags"] = filter_tag

        # Make the request
        response = self.session.get(f"{self.base_url}/rest/rules", params=params)
        response.raise_for_status()

        rules = json.loads(response.text)

        # Sort the rules
        reverse_sort = sort_order.lower() == "desc"
        rules.sort(
            key=lambda x: str(x["name"]).lower() if x["name"] else "",
            reverse=reverse_sort,
        )

        # Calculate pagination
        total_elements = len(rules)
        total_pages = (
            (total_elements + page_size - 1) // page_size if page_size > 0 else 1
        )
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        # Get the page of rules
        paginated_rules = rules[start_idx:end_idx]

        return {
            "rules": paginated_rules,
            "pagination": {
                "total_elements": total_elements,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": end_idx < total_elements,
                "has_previous": start_idx > 0,
            },
        }

    def get_rule_details(self, rule_uid: str) -> Optional[Dict[str, Any]]:
        """Get a specific rule by UID"""
        if rule_uid is None:
            return None

        try:
            response = self.session.get(f"{self.base_url}/rest/rules/{rule_uid}")
            response.raise_for_status()
            return json.loads(response.text)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def update_rule(self, rule_uid: str, rule_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing rule with partial updates"""
        # Check if rule exists
        current_rule = self.get_rule_details(rule_uid)
        if not current_rule:
            raise ValueError(f"Rule with UID '{rule_uid}' not found")

        # Merge with updates (only updating provided fields)
        for key, value in rule_updates.items():
            if key == "actions" and isinstance(value, list) and len(value) > 0:
                # Handle updating specific actions by ID
                for updated_action in value:
                    if "id" in updated_action:
                        # Find the matching action by ID and update it
                        for i, action in enumerate(current_rule["actions"]):
                            if action["id"] == updated_action["id"]:
                                # Update this specific action
                                current_rule["actions"][i].update(updated_action)
                                break
                        else:
                            # If no matching action found, append it
                            current_rule["actions"].append(updated_action)
                    else:
                        # No ID provided, just append the action
                        current_rule["actions"].append(updated_action)
            else:
                # For other fields, just update directly
                current_rule[key] = value

        # Send update request
        response = self.session.put(
            f"{self.base_url}/rest/rules/{rule_uid}", json=current_rule
        )
        response.raise_for_status()

        # Get the updated rule
        return self.get_rule_details(rule_uid)

    def update_rule_script_action(
        self, rule_uid: str, action_id: str, script_type: str, script_content: str
    ) -> Dict[str, Any]:
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

    def create_rule(self, rule: RuleDetails) -> Dict[str, Any]:
        """Create a new rule"""
        if not rule.uid:
            if self.generate_uids:
                rule.uid = self.generate_uid()
            else:
                raise ValueError("Rule must have a UID")

        # Prepare payload
        payload = rule.model_dump()

        # Send create request
        response = self.session.post(f"{self.base_url}/rest/rules", json=payload)
        response.raise_for_status()

        # Get the created rule
        return self.get_rule_details(rule.uid)

    def delete_rule(self, rule_uid: str) -> bool:
        """Delete a rule"""
        response = self.session.delete(f"{self.base_url}/rest/rules/{rule_uid}")

        if response.status_code == 404:
            raise ValueError(f"Rule with UID '{rule_uid}' not found")

        response.raise_for_status()
        return True

    def list_scripts(
        self,
        page: int = 1,
        page_size: int = 15,
        sort_order: str = "asc",
    ) -> Dict[str, Any]:
        """
        List all scripts. A script is a rule without a trigger and tag of 'Script'

        Args:
            page: 1-based page number (default: 1)
            page_size: Number of elements per page (default: 15)
            sort_order: Sort order ("asc" or "desc") (default: "asc")
        """
        return self.list_rules(
            page=page,
            page_size=page_size,
            sort_order=sort_order,
            filter_tag="Script",
        )

    def get_script_details(self, script_id: str) -> Dict[str, Any]:
        """Get a specific script by ID. A script is a rule without a trigger and tag of 'Script'"""
        if script_id is None:
            return None

        return self.get_rule_details(script_id)

    def create_script(
        self, script_id: str, script_type: str, content: str
    ) -> Dict[str, Any]:
        """Create a new script.  A script is a rule without a trigger and tag of 'Script'"""
        if not content:
            raise ValueError("Script content cannot be empty")
        if not script_type:
            raise ValueError("Script type cannot be empty")

        if not script_id:
            script_id = generate_uid()

        rule = RuleDetails(
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

    def update_script(
        self, script_id: str, script_type: str, content: str
    ) -> Dict[str, Any]:
        """Update an existing script. A script is a rule without a trigger and tag of 'Script'"""
        rule = self.get_rule_details(script_id)
        # Check if script exists
        if not rule:
            raise ValueError(f"Script with ID '{script_id}' not found")

        return self.update_rule_script_action(
            script_id, rule["actions"][0]["id"], script_type, content
        )

    def delete_script(self, script_id: str) -> bool:
        """Delete a script. A script is a rule without a trigger and tag of 'Script'"""
        return self.delete_rule(script_id)

    def run_rule_now(self, rule_uid: str) -> bool:
        """Run a rule immediately"""
        if not rule_uid:
            raise ValueError("Rule UID cannot be empty")

        # Check if rule exists
        if not self.get_rule_details(rule_uid):
            raise ValueError(f"Rule with UID '{rule_uid}' not found")

        # Send request to run the rule
        response = self.session.post(f"{self.base_url}/rest/rules/{rule_uid}/runnow")

        if response.status_code == 404:
            raise ValueError(f"Rule with UID '{rule_uid}' not found")

        response.raise_for_status()
        return True

    def list_tags(self, parent_tag_uid: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all tags

        Args:
            category: If provided, only return tags that belong to this category of tags (Location, Equipment, Point or Property)
            parent_tag_uid: If provided, only return tags that are a subtag of this tag

        Returns:
            List of tag dictionaries
        """
        response = self.session.get(f"{self.base_url}/rest/tags")
        response.raise_for_status()

        tags = json.loads(response.text)

        if category:
            tags = [tag for tag in tags if tag['uid'].lower().startswith(category.lower())]

        if parent_tag_uid:
            tags = [tag for tag in tags 
                   if tag['uid'] and tag['uid'].lower().startswith(f"{parent_tag_uid.lower()}_")]

        return tags

    def create_semantic_tag(self, tag: Tag) -> Dict[str, Any]:
        """Create a new semantic tag"""

        if self.get_tag(tag.uid):
            raise ValueError(f"Tag with UID '{tag.uid}' already exists")

        payload = tag.model_dump()

        response = self.session.post(f"{self.base_url}/rest/tags", json=payload)
        response.raise_for_status()

        # Get the created tag
        return next(iter(self.get_tag(tag.uid)))

    def get_tag(self, tag_uid: str, include_subtags: bool = False) -> Optional[List[Dict[str, Any]]]:
        """Get a specific tag by uid"""
        if tag_uid is None:
            return None

        try:
            response = self.session.get(f"{self.base_url}/rest/tags/{tag_uid}")
            response.raise_for_status()

            tags = json.loads(response.text)

            if not include_subtags:
                tags = [tag for tag in tags if tag['uid'] == tag_uid]

            return tags
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def delete_tag(self, tag_uid: str) -> bool:
        """
        Delete a tag by uid

        Args:
            tag_uid: UID of the tag to delete
        """
        response = self.session.delete(f"{self.base_url}/rest/tags/{tag_uid}")
        response.raise_for_status()
        return True

    def list_links(
        self,
        page: int = 1,
        page_size: int = 15,
        sort_order: str = "asc",
        item_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List links with pagination

        Args:
            page: 1-based page number
            page_size: Number of items per page
            sort_order: Sort order ("asc" or "desc")
            item_name: If provided, only return links that for the given item name

        Returns:
            PaginatedLinks object containing the paginated results and pagination info
        """

        params = {}
        if item_name:
            params["itemName"] = item_name

        # Get all links
        response = self.session.get(f"{self.base_url}/rest/links", params=params)
        response.raise_for_status()

        # Convert to Link objects
        links = json.loads(response.text)
        for link in links:
            match = re.match(r".*(?=:)", link["channelUID"])
            if match:
                link["thing_uid"] = match.group()
            else:
                link["thing_uid"] = None

        # Sort the links
        reverse_sort = sort_order.lower() == "desc"
        links.sort(
            key=lambda x: str(x['itemName'] + x['channelUID']).lower(), reverse=reverse_sort
        )

        # Calculate pagination
        total_elements = len(links)
        total_pages = (
            (total_elements + page_size - 1) // page_size if page_size > 0 else 1
        )
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        # Get the page of links
        paginated_links = links[start_idx:end_idx]

        return {
            "links": paginated_links,
            "pagination": {
                "total_elements": total_elements,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": end_idx < total_elements,
                "has_previous": start_idx > 0
            }
        }

    def get_link(self, item_name: str, channel_uid: str) -> Optional[Dict[str, Any]]:
        """Get a specific link by item name and channel UID"""
        if item_name is None or channel_uid is None:
            return None

        try:
            response = self.session.get(
                f"{self.base_url}/rest/links/{item_name}/{channel_uid.replace('#', '%23')}"
            )
            response.raise_for_status()

            return json.loads(response.text)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def create_link(self, link: Link) -> Link:
        """Create a new link"""
        if not link.itemName:
            raise ValueError("Link must have an item name")

        if not link.channelUID:
            raise ValueError("Link must have a channel UID")

        payload = link.model_dump()

        response = self.session.put(
            f"{self.base_url}/rest/links/{link.itemName}/{link.channelUID.replace('#', '%23')}",
            json=payload,
        )
        response.raise_for_status()

        # Get the created link
        return self.get_link(link.itemName, link.channelUID)

    def update_link(self, link: Link) -> Link:
        """Update an existing link"""
        if not link.itemName:
            raise ValueError("Link must have an item name")

        if not link.channelUID:
            raise ValueError("Link must have a channel UID")

        existing_link = self.get_link(
            link.itemName, link.channelUID.replace("#", "%23")
        )
        if not existing_link:
            raise ValueError(
                f"Link with item name '{link.itemName}' and channel UID '{link.channelUID}' not found"
            )

        created_link = self.create_link(link)

        # Get the updated link
        return created_link

    def delete_link(self, item_name: str, channel_uid: str) -> bool:
        """Delete an existing link"""
        if item_name is None or channel_uid is None:
            return False

        try:
            response = self.session.delete(
                f"{self.base_url}/rest/links/{item_name}/{channel_uid.replace('#', '%23')}"
            )
            response.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return False
            raise

    def get_item_persistence(
        self, item_name: str, starttime: str = None, endtime: str = None
    ) -> ItemPersistence:
        """
        Get the persistence state values of an item between starttime and endtime
        in zulu time format [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']
        """

        if not item_name:
            raise ValueError("Item name must be provided")

        params = {}
        if starttime:
            if not DATE_PATTERN.match(starttime):
                raise ValueError(f"Start time must be in format {DATE_PATTERN.pattern}")
            params["starttime"] = starttime

        if endtime:
            if not DATE_PATTERN.match(endtime):
                raise ValueError(f"End time must be in format {DATE_PATTERN.pattern}")
            params["endtime"] = endtime

        try:
            response = self.session.get(
                f"{self.base_url}/rest/persistence/items/{item_name}", params=params
            )
            response.raise_for_status()
            return ItemPersistence(**response.json())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def delete_item(self, item_name: str) -> bool:
        """Delete an item"""
        response = self.session.delete(f"{self.base_url}/rest/items/{item_name}")

        if response.status_code == 404:
            raise ValueError(f"Item with name '{item_name}' not found")
        response.raise_for_status()
        return True
