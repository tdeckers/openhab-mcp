import re
import requests
import random
import string
from typing import Dict, List, Optional, Any

from models import (
    Item,
    ItemDetails,
    ItemMetadata,
    Link,
    Thing,
    ThingDetails,
    Tag,
    PaginatedThings,
    PaginatedItems,
    PaginatedLinks,
    PaginationInfo,
    PaginatedRules,
    Rule,
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

    def list_items(
        self,
        page: int = 1,
        page_size: int = 15,
        sort_by: str = "name",
        sort_order: str = "asc",
        filter_tag: Optional[str] = None,
        filter_type: Optional[str] = None,
    ) -> PaginatedItems:
        """
        List items with pagination

        Args:
            page: 1-based page number
            page_size: Number of items per page
            sort_by: Field to sort by (e.g., "label", "thingTypeUID")
            sort_order: Sort order ("asc" or "desc")

        Returns:
            PaginatedItems object containing the paginated results and pagination info
        """
        # Get all items
        params = {}
        if filter_tag:
            params["tags"] = filter_tag
        if filter_type:
            params["type"] = filter_type

        response = self.session.get(f"{self.base_url}/rest/items", params=params)
        response.raise_for_status()

        # Convert to Item objects
        items = [Item(**item) for item in response.json()]

        # Sort the items
        reverse_sort = sort_order.lower() == "desc"
        try:
            items.sort(
                key=lambda x: (
                    str(getattr(x, sort_by, "")).lower() if hasattr(x, sort_by) else ""
                ),
                reverse=reverse_sort,
            )
        except Exception as e:
            # Fallback to default sort if the requested sort field doesn't exist
            items.sort(
                key=lambda x: str(x.name).lower() if x.name else "",
                reverse=reverse_sort,
            )

        # Calculate pagination
        total_elements = len(items)
        total_pages = (
            (total_elements + page_size - 1) // page_size if page_size > 0 else 1
        )
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        # Get the page of items
        paginated_items = items[start_idx:end_idx]

        return PaginatedItems(
            items=paginated_items,
            pagination=PaginationInfo(
                total_elements=total_elements,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                has_next=end_idx < total_elements,
                has_previous=start_idx > 0,
            ),
        )

    def list_locations(
        self,
        page: int = 1,
        page_size: int = 15,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> PaginatedItems:
        """
        List locations with pagination

        Args:
            page: 1-based page number
            page_size: Number of items per page
            sort_by: Field to sort by (e.g., "name")
            sort_order: Sort order ("asc" or "desc")

        Returns:
            PaginatedItems object containing the paginated results and pagination info
        """
        # Get all locations
        locations = self.list_items(
            page, page_size, sort_by, sort_order, filter_tag="Location"
        )

        return locations

    def get_item_details(
        self, item_name: str, include_members: bool = False
    ) -> Optional[ItemDetails]:
        """Get a specific item by name"""
        if item_name is None:
            return None

        params = {}
        if include_members:
            params["recursive"] = "true"
        else:
            params["recursive"] = "false"

        try:
            response = self.session.get(
                f"{self.base_url}/rest/items/{item_name}", params=params
            )
            response.raise_for_status()
            return ItemDetails(**response.json())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def create_item(self, item: ItemDetails) -> ItemDetails:
        """Create a new item"""
        if not item.name:
            raise ValueError("Item must have a name")

        payload = item.model_dump()

        response = self.session.put(
            f"{self.base_url}/rest/items/{item.name}", json=payload
        )
        response.raise_for_status()

        # Get the created item
        return self.get_item_details(item.name)

    def create_item_metadata(
        self, item_name: str, namespace: str, metadata: ItemMetadata
    ) -> ItemDetails:
        """Create metadata for a specific item"""

        item = self.get_item_details(item_name)
        if namespace in item.metadata:
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

        return self.get_item_details(item_name)

    def update_item_metadata(
        self, item_name: str, namespace: str, metadata: ItemMetadata
    ) -> ItemDetails:
        """Update metadata for a specific item"""

        item = self.get_item_details(item_name)
        if namespace not in item.metadata:
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

        return self.get_item_details(item_name)

    def update_item(self, item_name: str, item: ItemDetails) -> ItemDetails:
        """Update an existing item"""
        # Get current item to merge with updates
        current_item = self.get_item_details(item_name)
        if not current_item:
            raise ValueError(f"Item with name '{item_name}' not found")
        if (
            item.transformedState
            and item.transformedState != current_item.transformedState
        ):
            raise ValueError(
                f"Cannot update transformedState of item '{item_name}'. Update state instead."
            )

        # Prepare update payload
        payload = {
            "type": item.type or current_item.type,
            "name": item_name,
            "state": item.state or current_item.state,
            "label": item.label or current_item.label,
            "category": item.category or current_item.category,
            "tags": item.tags or current_item.tags,
            "groupNames": item.groupNames or current_item.groupNames,
            "members": item.members or current_item.members,
            "metadata": item.metadata or current_item.metadata,
            "commandDescription": item.commandDescription
            or current_item.commandDescription,
            "stateDescription": item.stateDescription or current_item.stateDescription,
            "unitSymbol": item.unitSymbol or current_item.unitSymbol,
        }

        response = self.session.put(
            f"{self.base_url}/rest/items/{item_name}", json=payload
        )
        response.raise_for_status()

        # Get the updated item
        return self.get_item_details(item_name)

    def get_item_persistence(
        self, item_name: str, starttime: str = None, endtime: str = None
    ) -> ItemPersistence:
        """
        Get the persistence state values of an item between starttime and endtime
        in zulu time format [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']
        """

        if item_name is None:
            return None

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

    def update_item_state(self, item_name: str, state: str) -> ItemDetails:
        """Update just the state of an item"""
        # Check if item exists
        if not self.get_item_details(item_name):
            raise ValueError(f"Item with name '{item_name}' not found")

        # Update state
        response = self.session.post(
            f"{self.base_url}/rest/items/{item_name}",
            data=state,
            headers={"Content-Type": "text/plain"},
        )
        response.raise_for_status()

        # Get the updated item
        return self.get_item_details(item_name)

    def list_things(
        self,
        page: int = 1,
        page_size: int = 15,
        sort_by: str = "UID",
        sort_order: str = "asc",
    ) -> PaginatedThings:
        """
        List things with pagination

        Args:
            page: 1-based page number
            page_size: Number of items per page
            sort_by: Field to sort by (e.g., "label", "thingTypeUID")
            sort_order: Sort order ("asc" or "desc")

        Returns:
            PaginatedThings object containing the paginated results and pagination info
        """
        # Get all things
        response = self.session.get(f"{self.base_url}/rest/things")
        response.raise_for_status()

        # Convert to Thing objects
        things = [Thing(**thing) for thing in response.json()]

        # Sort the things
        reverse_sort = sort_order.lower() == "desc"
        try:
            things.sort(
                key=lambda x: (
                    str(getattr(x, sort_by, "")).lower() if hasattr(x, sort_by) else ""
                ),
                reverse=reverse_sort,
            )
        except Exception as e:
            # Fallback to default sort if the requested sort field doesn't exist
            things.sort(
                key=lambda x: str(x.UID).lower() if x.UID else "", reverse=reverse_sort
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

        return PaginatedThings(
            things=paginated_items,
            pagination=PaginationInfo(
                total_elements=total_elements,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                has_next=end_idx < total_elements,
                has_previous=start_idx > 0,
            ),
        )

    def get_thing_details(self, thing_uid: str) -> Optional[ThingDetails]:
        """Get a specific thing by UID"""
        if thing_uid is None:
            return None

        try:
            response = self.session.get(f"{self.base_url}/rest/things/{thing_uid}")
            response.raise_for_status()
            return ThingDetails(**response.json())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def create_thing(self, thing: Thing) -> ThingDetails:
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
        return self.get_thing_details(thing.UID)

    def update_thing(self, thing_uid: str, thing: ThingDetails) -> ThingDetails:
        """Update an existing thing"""
        # Get current thing to merge with updates
        current_thing = self.get_thing_details(thing_uid)
        if not current_thing:
            raise ValueError(f"Thing with UID '{thing_uid}' not found")

        # Prepare update payload
        payload = {
            "thingTypeUID": thing.thingTypeUID,
            "UID": thing_uid,
            "label": thing.label or current_thing.label,
            "configuration": thing.configuration or current_thing.configuration,
            "properties": thing.properties or current_thing.properties,
            "channels": thing.channels or current_thing.channels,
        }

        response = self.session.put(
            f"{self.base_url}/rest/things/{thing_uid}", json=payload
        )
        response.raise_for_status()

        # Get the updated thing
        return self.get_thing_details(thing_uid)

    def delete_thing(self, thing_uid: str) -> bool:
        """Delete a thing"""
        response = self.session.delete(f"{self.base_url}/rest/things/{thing_uid}")

        if response.status_code == 404:
            raise ValueError(f"Thing with UID '{thing_uid}' not found")

        response.raise_for_status()
        return True

    def list_rules(
        self,
        page: int = 1,
        page_size: int = 15,
        sort_by: str = "name",
        sort_order: str = "asc",
        filter_tag: Optional[str] = None,
    ) -> PaginatedRules:
        """
        List all rules, optionally filtered by tag

        Args:
            page: 1-based page number (default: 1)
            page_size: Number of elements per page (default: 15)
            sort_by: Field to sort by (e.g., "name", "label") (default: "name")
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

        rules = [Rule(**rule) for rule in response.json()]

        # Sort the rules
        reverse_sort = sort_order.lower() == "desc"
        try:
            rules.sort(
                key=lambda x: (
                    str(getattr(x, sort_by, "")).lower() if hasattr(x, sort_by) else ""
                ),
                reverse=reverse_sort,
            )
        except Exception:
            # Fallback to default sort if the requested sort field doesn't exist
            rules.sort(
                key=lambda x: str(x.name).lower() if x.name else "",
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

        return PaginatedRules(
            rules=paginated_rules,
            pagination=PaginationInfo(
                total_elements=total_elements,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                has_next=end_idx < total_elements,
                has_previous=start_idx > 0,
            ),
        )

    def get_rule_details(self, rule_uid: str) -> Optional[RuleDetails]:
        """Get a specific rule by UID"""
        if rule_uid is None:
            return None

        try:
            response = self.session.get(f"{self.base_url}/rest/rules/{rule_uid}")
            response.raise_for_status()
            return RuleDetails(**response.json())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def update_rule(self, rule_uid: str, rule_updates: Dict[str, Any]) -> RuleDetails:
        """Update an existing rule with partial updates"""
        # Check if rule exists
        current_rule = self.get_rule_details(rule_uid)
        if not current_rule:
            raise ValueError(f"Rule with UID '{rule_uid}' not found")

        # Get the current rule as a dictionary
        current_rule_dict = current_rule.model_dump()

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
        return self.get_rule_details(rule_uid)

    def update_rule_script_action(
        self, rule_uid: str, action_id: str, script_type: str, script_content: str
    ) -> RuleDetails:
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

    def create_rule(self, rule: RuleDetails) -> RuleDetails:
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
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> PaginatedRules:
        """
        List all scripts. A script is a rule without a trigger and tag of 'Script'

        Args:
            page: 1-based page number (default: 1)
            page_size: Number of elements per page (default: 15)
            sort_by: Field to sort by (e.g., "name", "label") (default: "name")
            sort_order: Sort order ("asc" or "desc") (default: "asc")
        """
        return self.list_rules(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            filter_tag="Script",
        )

    def get_script_details(self, script_id: str) -> Optional[RuleDetails]:
        """Get a specific script by ID. A script is a rule without a trigger and tag of 'Script'"""
        if script_id is None:
            return None

        return self.get_rule_details(script_id)

    def create_script(
        self, script_id: str, script_type: str, content: str
    ) -> RuleDetails:
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
    ) -> RuleDetails:
        """Update an existing script. A script is a rule without a trigger and tag of 'Script'"""
        rule = self.get_rule_details(script_id)
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
        if not self.get_rule_details(rule_uid):
            raise ValueError(f"Rule with UID '{rule_uid}' not found")

        # Send request to run the rule
        response = self.session.post(f"{self.base_url}/rest/rules/{rule_uid}/runnow")

        if response.status_code == 404:
            raise ValueError(f"Rule with UID '{rule_uid}' not found")

        response.raise_for_status()
        return True

    def list_tags(self, parent_tag_uid: Optional[str] = None) -> List[Tag]:
        """
        List all tags

        Args:
            parent_tag_uid: If provided, only return tags that are a subtag of this tag

        Returns:
            List of tags
        """
        response = self.session.get(f"{self.base_url}/rest/tags")
        response.raise_for_status()

        tags = [Tag(**tag) for tag in response.json()]

        if parent_tag_uid:
            tags = [tag for tag in tags if tag.uid.startswith(f"{parent_tag_uid}_")]

        return tags

    def create_tag(self, tag: Tag) -> Tag:
        """Create a new tag"""
        if not tag.name:
            raise ValueError("Tag must have a name")

        if not tag.uid:
            raise ValueError("Tag must have a uid")

        payload = tag.model_dump()

        response = self.session.post(f"{self.base_url}/rest/tags", json=payload)
        response.raise_for_status()

        # Get the created tag
        return self.get_tag(tag.uid)

    def get_tag(self, tag_uid: str) -> Optional[Tag]:
        """Get a specific tag by uid"""
        if tag_uid is None:
            return None

        try:
            response = self.session.get(f"{self.base_url}/rest/tags/{tag_uid}")
            response.raise_for_status()

            tags = [Tag(**tag) for tag in response.json()]
            return next((tag for tag in tags if tag.uid == tag_uid), None)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def list_links(
        self,
        page: int = 1,
        page_size: int = 15,
        sort_order: str = "asc",
        item_name: Optional[str] = None,
    ) -> PaginatedLinks:
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
        links = [Link(**link) for link in response.json()]

        # Sort the links
        reverse_sort = sort_order.lower() == "desc"
        links.sort(
            key=lambda x: str(x.itemName + x.channelUID).lower(), reverse=reverse_sort
        )

        # Calculate pagination
        total_elements = len(links)
        total_pages = (
            (total_elements + page_size - 1) // page_size if page_size > 0 else 1
        )
        print("Page: " + str(page))
        print("Page size: " + str(page_size))
        print("Total elements: " + str(total_elements))
        print("Total pages: " + str(total_pages))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        # Get the page of links
        paginated_links = links[start_idx:end_idx]

        return PaginatedLinks(
            links=paginated_links,
            pagination=PaginationInfo(
                total_elements=total_elements,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                has_next=end_idx < total_elements,
                has_previous=start_idx > 0,
            ),
        )

    def get_link(self, item_name: str, channel_uid: str) -> Optional[Link]:
        """Get a specific link by item name and channel UID"""
        if item_name is None or channel_uid is None:
            return None

        try:
            response = self.session.get(
                f"{self.base_url}/rest/links/{item_name}/{channel_uid.replace('#', '%23')}"
            )
            response.raise_for_status()

            return Link(**response.json())
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