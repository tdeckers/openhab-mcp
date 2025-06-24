import re
import requests
import random
import string
from typing import Dict, List, Optional, Any, Set
from pydantic import create_model
import json
from pydantic import Field

# Update imports
from models import (
    ItemBase,
    ItemCreate,
    ItemMetadata,
    Link,
    ThingBase,
    ThingCreate,
    Tag,
    RuleCreate, 
    RuleUpdate
)


DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


class OpenHABClient:
    """Client for interacting with the openHAB REST API"""

    # ===== Initialization & Authentication =====
    def __init__(
        self,
        base_url: str,
        api_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
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

    # ===== Items =====
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
        tags = self.list_semantic_tags()

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
            if ("semanticTags" in output_fields or "nonSemanticTags" in output_fields):
                api_fields.update(["tags"])
                
            # Add other requested fields
            if output_fields:
                api_fields.update(f for f in output_fields if f not in ["semanticTags", "nonSemanticTags"])
                
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

    def get_item(self, item_name: str) -> Dict[str, Any]:
        """
        Get a single item by name

        Args:
            item_name: Name of the item to get

        Returns:
            Dict[str, Any]: The item with the given name

        Raises:
            ValueError: If the item with the given name does not exist
        """
        result = self.list_items(filter_name=item_name, page_size=1)
        if not result["items"]:
            raise ValueError(f"Item with name '{item_name}' not found")
        
        return result["items"][0]

    def create_item(self, item: ItemCreate) -> Dict[str, Any]:
        """
        Create a new item

        Args:
            item: The item to create

        Returns:
            Dict[str, Any]: The created item

        Raises:
            ValueError: If the item with the given name already exists
        """

        payload = item.model_dump(exclude_unset=True, by_alias=True)
        # Not part of the create item API. Is handled later
        payload.pop("metadata", None)
        payload.pop("groupNames", None)
        
        # Handle tags
        payload["tags"] = []
        if "semanticTags" in payload:
            tags = self.list_semantic_tags()
            for tag in tags:
                if tag["uid"] in payload["semanticTags"]:
                    payload["tags"].append(tag["name"])
            del payload["semanticTags"]
        if "nonSemanticTags" in payload:
            payload["tags"] += payload["nonSemanticTags"]
            del payload["nonSemanticTags"]

        response = self.session.put(
            f"{self.base_url}/rest/items/{item.name}", json=payload
        )
        if response.status_code == 400:
            raise ValueError("Invalid item payload")
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item.name}' not found")
        if response.status_code == 405:
            raise ValueError(f"Item with name '{item.name}' not editable")
        response.raise_for_status()

        errors = []
        if item.metadata:
            for namespace, metadata in item.metadata.items():
                try:
                    self.add_or_update_item_metadata(item.name, namespace, metadata)
                except ValueError as e:
                    errors.append(str(e))
        if item.group_names:
            for group_name in item.group_names:
                try:
                    self.add_item_member(group_name, item.name)
                except ValueError as e:
                    errors.append(str(e))
        
        if errors:
            raise ValueError("Item created successfully but some metadata or group assignments failed:\n" + "\n".join(errors))

        # Get the created item
        return self.get_item(item.name)

    def update_item(self, item: ItemBase) -> Dict[str, Any]:
        """
        Update an existing item by merging changes with its current state

        Args:
            item: The item containing updates to apply

        Returns:
            Dict[str, Any]: The updated item

        Raises:
            ValueError: If the item with the given name does not exist or update fails
        """
        # Get current item state as a dictionary
        payload = self.get_item(item.name)
        
        # Convert the update item to a dictionary, excluding unset fields
        update_data = item.model_dump(exclude_unset=True, by_alias=True)
        
        # Handle semantic and non-semantic tags from the update
        if 'semanticTags' in update_data or 'nonSemanticTags' in update_data:
            tags = []
            if 'semanticTags' in update_data:
                all_tags = self.list_semantic_tags()
                for tag in all_tags:
                    if tag["uid"] in update_data["semanticTags"]:
                        tags.append(tag["name"])
            if 'nonSemanticTags' in update_data:
                tags.extend(update_data['nonSemanticTags'])
            payload['tags'] = tags
            
            # Remove the original fields as they're not part of the API
            update_data.pop('semanticTags', None)
            update_data.pop('nonSemanticTags', None)

        # Update payload with values from update_data
        payload.update(update_data)
        
        # Send the update
        response = self.session.put(
            f"{self.base_url}/rest/items/{item.name}",
            json=payload
        )
        
        if response.status_code == 400:
            raise ValueError("Invalid item payload")
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item.name}' not found")
        if response.status_code == 405:
            raise ValueError(f"Item with name '{item.name}' not editable")
        response.raise_for_status()

        # Return the updated item
        return self.get_item(item.name)
    
    def delete_item(self, item_name: str) -> bool:
        """
        Delete an item

        Args:
            item_name: Name of the item to delete

        Returns:
            True if the item was deleted, raises an error otherwise

        Raises:
            ValueError: If the item with the given name does not exist or is not editable
        """
        if not item_name:
            raise ValueError("Item name must be provided")

        response = self.session.delete(f"{self.base_url}/rest/items/{item_name}")
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item_name}' not found")
        
        response.raise_for_status()
        return True

    # Item State Management
    def get_item_state(self, item_name: str) -> str:
        """
        Get the state of an item

        Args:
            item_name: Name of the item to get the state of

        Returns:
            str: The state of the item

        Raises:
            ValueError: If the item with the given name does not exist
        """
        response = self.session.get(f"{self.base_url}/rest/items/{item_name}/state")
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item_name}' not found")
        
        response.raise_for_status()
        return response.text

    def update_item_state(self, item_name: str, state: str) -> Dict[str, Any]:
        """
        Update just the state of an item

        Args:
            item_name: Name of the item to update state for
            state: State to update the item to. Allowed states depend on the item type

        Returns:
            bool: True if the item was updated, raises an error otherwise

        Raises:
            ValueError: If the item with the given name does not exist or update fails
        """
        # Check if item exists using list_items with name filter
        if not item_name:
            raise ValueError("Item name must be provided")
        if not state:
            raise ValueError("State must be provided")

        # Update state
        response = self.session.put(
            f"{self.base_url}/rest/items/{item_name}/state",
            data=state,
            headers={"Content-Type": "text/plain"},
        )
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item_name}' not found")
        response.raise_for_status()

        return True

    def send_command(self, item_name: str, command: str) -> Dict[str, Any]:
        """
        Send a command to an item

        Args:
            item_name: Name of the item to send the command to
            command: Command to send to the item. Allowed commands depend on the item type

        Returns:
            bool: True if the command was sent, raises an error otherwise

        Raises:
            ValueError: If the item with the given name does not exist or command fails
        """
        # Check if item exists using list_items with name filter
        if not item_name:
            raise ValueError("Item name must be provided")
        if not command:
            raise ValueError("Command must be provided")

        # Send command
        response = self.session.post(
            f"{self.base_url}/rest/items/{item_name}",
            data=command,
            headers={"Content-Type": "text/plain"},
        )
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item_name}' not found")
        response.raise_for_status()

        return True

    def get_item_persistence(
        self, item_name: str, starttime: str = None, endtime: str = None
    ) -> Dict[str, Any]:
        """
        Get the persistence state values of an item between starttime and endtime
        in zulu time format [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']

        Args:
            item_name: Name of the item to get persistence for
            starttime: Start time in zulu time format [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']
            endtime: End time in zulu time format [yyyy-MM-dd'T'HH:mm:ss.SSS'Z']

        Returns:
            Dict[str, Any]: The persistence state values of the item between starttime and endtime

        Raises:
            ValueError: If the item with the given name does not exist or persistence service is not found
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

            response = self.session.get(
                f"{self.base_url}/rest/persistence/items/{item_name}", params=params
            )
            if response.status_code == 404:
                raise ValueError(f"Item with name '{item_name}' not found or persistence service not found")

            response.raise_for_status()
            return response.json()

    # ===== Item Metadata =====
    def get_item_metadata_namespaces(self, item_name: str) -> List[str]:
        """
        Get the namespaces of metadata for a specific openHAB item.

        Args:
            item_name: Name of the item to get metadata namespaces for

        Returns:
            List[str]: A list of metadata namespaces

        Raises:
            ValueError: If no item name is provided or item with the given name does not exist
        """
        # Check if item exists using list_items with name filter
        if not item_name:
            raise ValueError("Item name must be provided")

        # Get metadata namespaces
        response = self.session.get(f"{self.base_url}/rest/items/{item_name}/metadata/namespaces")
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item_name}' not found")

        response.raise_for_status()
        return response.json()

    def add_or_update_item_metadata(
        self, item_name: str, namespace: str, metadata: ItemMetadata
    ) -> Dict[str, Any]:
        """
        Add new metadata for a specific openHAB item.

        Args:
            item_name: Name of the item to create metadata for
            namespace: Namespace for the metadata (must be unique per item)
            metadata: ItemMetadata object containing the metadata value and config

        Returns:
            Dict[str, Any]: A dictionary containing the updated item data

        Raises:
            ValueError: If the metadata is invalid, the namespace already exists, 
                       or if the namespace is 'semantics'
        """
        if not item_name:
            raise ValueError("Item name must be provided")
        if not namespace:
            raise ValueError("Namespace must be provided")
            
        # Validate that the namespace is not 'semantics'
        if namespace == "semantics":
            raise ValueError(
                "The 'semantics' namespace is a reserved namespace for openHAB semantic tags. "
                "Please assign tags or change group membership to change the item semantics."
            )

        payload = metadata.model_dump(exclude_unset=True, by_alias=True)

        response = self.session.put(
            f"{self.base_url}/rest/items/{item_name}/metadata/{namespace}", json=payload
        )
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item_name}' not found")
        if response.status_code == 405:
            raise ValueError(f"Metadata namespace '{namespace}' for item '{item_name}' not editable")
        response.raise_for_status()

        return self.get_item(item_name)
    
    def remove_item_metadata(self, item_name: str, namespace: str) -> bool:
        """
        Remove metadata for a specific item

        Args:
            item_name: Name of the item to remove metadata for
            namespace: Namespace for the metadata
        Returns:
            bool: True if the metadata was removed, raises an error otherwise
        Raises:
            ValueError: If the metadata is invalid or the namespace does not exist
        """
        if not item_name:
            raise ValueError("Item name must be provided")
        if not namespace:
            raise ValueError("Namespace must be provided")
        
        # Validate that the namespace is not 'semantics'
        if namespace == "semantics":
            raise ValueError(
                "The 'semantics' namespace is a reserved namespace for openHAB semantic tags. "
                "Please remove tags or change group membership to change the item semantics."
            )
        response = self.session.delete(
            f"{self.base_url}/rest/items/{item_name}/metadata/{namespace}"
        )
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item_name}' not found")
        if response.status_code == 405:
            raise ValueError(f"Metadata namespace '{namespace}' for item '{item_name}' not editable")

        response.raise_for_status()
        return self.get_item(item_name)
    
    # ===== Item Members (Group Management) =====
    def add_item_member(self, item_name: str, member_item_name: str) -> Dict[str, Any]:
        """
        Add a member to an item (group).

        Args:
            item_name: Name of the parent item (group)
            member_item_name: Name of the member item to add

        Returns:
            The complete updated item

        Raises:
            ValueError: If the item with the given name does not exist or is not a group item
            ValueError: If the member item with the given name does not exist or is not editable
        """
        if not item_name:
            raise ValueError("Item name must be provided")
        if not member_item_name:
            raise ValueError("Member item name must be provided")

        response = self.session.put(f"{self.base_url}/rest/items/{item_name}/members/{member_item_name}")
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item_name}' not found or is not a group item")
        if response.status_code == 405:
            raise ValueError(f"Item with name '{member_item_name}' is not editable")
        
        response.raise_for_status()
        return self.get_item(item_name)

    def remove_item_member(self, item_name: str, member_item_name: str) -> Dict[str, Any]:
        """
        Remove a member from an item (group).

        Args:
            item_name: Name of the parent item (group)
            member_item_name: Name of the member item to remove

        Returns:
            The complete updated item

        Raises:
            ValueError: If the item with the given name does not exist or is not a group item
            ValueError: If the member item with the given name does not exist or is not editable
        """
        if not item_name:
            raise ValueError("Item name must be provided")
        if not member_item_name:
            raise ValueError("Member item name must be provided")

        response = self.session.delete(f"{self.base_url}/rest/items/{item_name}/members/{member_item_name}")
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item_name}' not found or is not a group item")
        if response.status_code == 405:
            raise ValueError(f"Item with name '{member_item_name}' is not editable")
        
        response.raise_for_status()
        return self.get_item(item_name)

    # ===== Links =====
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
            item_name: If provided, only return links for the given item name

        Returns:
            PaginatedLinks object containing the paginated results and pagination info
        """

        params = {}
        if item_name:
            params["itemName"] = item_name

        # Get all links
        response = self.session.get(f"{self.base_url}/rest/links", params=params)
        response.raise_for_status()

        links = response.json()
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

    def get_link(self, item_name: str, channel_uid: str) -> Dict[str, Any]:
        """
        Get a specific link by item name and channel UID

        Args:
            item_name: Name of the item
            channel_uid: UID of the channel

        Returns:
            Link object containing the link details
        """
        if not item_name:
            raise ValueError("Item name must be provided")

        if not channel_uid:
            raise ValueError("Channel UID must be provided")

        response = self.session.get(
            f"{self.base_url}/rest/links/{item_name}/{channel_uid.replace('#', '%23')}"
        )
        if response.status_code == 404:
            raise ValueError(f"Link between item '{item_name}' and channel '{channel_uid}' not found")

        response.raise_for_status()
        return response.json()
    
    def create_or_update_link(self, link: Link) -> Dict[str, Any]:
        """
        Create a new link or update an existing one

        Args:
            link: Link object to create or update

        Returns:
            Created link object

        Raises:
            ValueError: If the link between the item name and channel UID is not editable
        """
        payload = link.model_dump(exclude_unset=True, by_alias=True)

        response = self.session.put(
            f"{self.base_url}/rest/links/{link.itemName}/{link.channelUID.replace('#', '%23')}",
            json=payload,
        )
        if response.status_code == 400:
            raise ValueError(f"Link between item '{link.itemName}' and channel '{link.channelUID}' not found or link is not editable")
        
        response.raise_for_status()
        return self.get_link(link.itemName, link.channelUID)

    def delete_link(self, item_name: str, channel_uid: str) -> bool:
        """
        Delete an existing link

        Args:
            item_name: Name of the item to delete the link for
            channel_uid: UID of the channel to delete the link for

        Returns:
            True if the link was deleted, raises an error otherwise

        Raises:
            ValueError: If the item name or channel UID is not provided
            ValueError: If the link between the item name and channel UID is not found
        """
        if not item_name:
            raise ValueError("Item name must be provided")

        if not channel_uid:
            raise ValueError("Channel UID must be provided")

        response = self.session.delete(
            f"{self.base_url}/rest/links/{item_name}/{channel_uid.replace('#', '%23')}"
        )
        if response.status_code == 404:
            raise ValueError(f"Link between item name '{item_name}' and channel UID '{channel_uid}' not found")
        
        response.raise_for_status()
        return True

    # ===== Things =====
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
        things = response.json()
        # The responses are too long to be handled by most LLMs so we remove the channels
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

    def get_thing(self, thing_uid: str) -> Dict[str, Any]:
        """
        Get a specific thing by UID

        Args:
            thing_uid: UID of the thing to retrieve

        Returns:
            Thing object containing the thing details
        """
        response = self.session.get(f"{self.base_url}/rest/things/{thing_uid}")
        if response.status_code == 404:
            raise ValueError(f"Thing with UID '{thing_uid}' not found")

        response.raise_for_status()
        thing = response.json()
        # The responses are too long to be handled by most LLMs so we remove the channels
        thing.pop('channels', None)
        return thing

    def create_thing(self, thing: ThingCreate) -> Dict[str, Any]:
        """
        Create a new thing

        Args:
            thing: Thing object to create

        Returns:
            Created thing object
        """
        payload = thing.model_dump(exclude_unset=True, by_alias=True)
        response = self.session.post(f"{self.base_url}/rest/things", json=payload)
        if response.status_code == 400:
            raise ValueError("A UID must be provided if no binding can create a thing of this type.")
        if response.status_code == 409:
            raise ValueError(f"A thing with the UID '{thing.UID}' already exists.")

        response.raise_for_status()
        return self.get_thing(thing.UID)

    def update_thing(self, thing: ThingBase) -> Dict[str, Any]:
        """
        Update an existing thing by merging changes with its current state

        Args:
            thing: The thing containing updates to apply

        Returns:
            Dict[str, Any]: The updated thing

        Raises:
            ValueError: If the thing with the given UID does not exist or update fails
        """
        # Get current thing state as a dictionary
        payload = self.get_thing(thing.UID)
        
        # Convert the update thing to a dictionary, excluding unset fields
        update_data = thing.model_dump(exclude_unset=True, by_alias=True)
        
        # Update payload with values from update_data
        payload.update(update_data)
        
        # Send the update
        response = self.session.put(
            f"{self.base_url}/rest/things/{thing.UID}",
            json=payload
        )
        
        if response.status_code == 404:
            raise ValueError(f"Thing with UID '{thing.UID}' not found")
        if response.status_code == 409:
            raise ValueError(f"Thing with UID '{thing.UID}' not editable")
        response.raise_for_status()

        # Return the updated thing
        return self.get_thing(thing.UID)

    def delete_thing(self, thing_uid: str) -> bool:
        """Delete a thing"""
        response = self.session.delete(f"{self.base_url}/rest/things/{thing_uid}")

        if response.status_code == 404:
            raise KeyError(f"Thing with UID '{thing_uid}' not found")

        response.raise_for_status()
        return True

    # Thing Channels
    def get_thing_channels(self, thing_uid: str, linked_only: bool = False) -> Optional[List[Dict[str, Any]]]:
        """Get the channels of a specific thing by UID
        
        Args:
            thing_uid: The UID of the thing
            linked_only: If True, only return channels with linked items
                        If False, return all channels (default)
                        
        Returns:
            List of channel dictionaries, or None if thing not found
        """
        if not thing_uid:
            raise ValueError("Thing UID must be provided")

        response = self.session.get(f"{self.base_url}/rest/things/{thing_uid}")
        if response.status_code == 404:
            raise ValueError(f"Thing with UID '{thing_uid}' not found")

        response.raise_for_status()
        channels = response.json().get("channels", [])        
        if linked_only:
            return [channel for channel in channels if channel.get("linkedItems")]
        return channels


    # ===== Rules =====
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

    def get_rule(self, rule_uid: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific rule by UID

        Args:
            rule_uid: UID of the rule to retrieve

        Returns:
            Dict[str, Any]: The rule details
        """
        if not rule_uid:
            raise ValueError("Rule UID must be provided")

        response = self.session.get(f"{self.base_url}/rest/rules/{rule_uid}")
        if response.status_code == 404:
            raise ValueError(f"Rule with UID '{rule_uid}' not found")

        response.raise_for_status()
        return response.json()

    def create_rule(self, rule: RuleCreate) -> Dict[str, Any]:
        """
        Create a new rule

        Args:
            rule: Rule object to create

        Returns:
            Dict[str, Any]: The created rule
        """
        # Prepare payload
        payload = rule.model_dump(exclude_unset=True, by_alias=True)
        
        # Send create request
        response = self.session.post(f"{self.base_url}/rest/rules", json=payload)
        if response.status_code == 400:
            raise ValueError("Rule is missing required parameters")
        if response.status_code == 409:
            raise ValueError(f"A rule with the UID '{rule.uid}' already exists")

        response.raise_for_status()
        return self.get_rule(rule.uid)

    def update_rule(self, rule: RuleUpdate) -> Dict[str, Any]:
        """
        Update an existing rule by merging changes with its current state

        Args:
            rule: The rule containing updates to apply

        Returns:
            Dict[str, Any]: The updated rule

        Raises:
            ValueError: If the rule with the given UID does not exist or update fails
        """
        if not rule.uid:
            raise ValueError("Rule UID must be provided")

        # Get current rule state. This raises an error if the rule does not exist so no need to handle that after the update
        current_rule = self.get_rule(rule.uid)
        
        # Convert the update rule to a dictionary, excluding unset fields
        update_data = rule.model_dump(exclude_unset=True, by_alias=True)
        
        # Handle actions specially since they can be updated by ID
        if 'actions' in update_data and update_data['actions']:
            # Create a mapping of action IDs to their indices for faster lookup
            action_map = {action['id']: i for i, action in enumerate(current_rule['actions'])}
            
            # Update or add each action from the update
            for updated_action in update_data['actions']:
                if 'id' in updated_action and updated_action['id'] in action_map:
                    # Update existing action
                    idx = action_map[updated_action['id']]
                    current_rule['actions'][idx].update(updated_action)
                else:
                    # Add new action
                    current_rule['actions'].append(updated_action)
            
            # Remove the actions from update_data to prevent overwriting our changes
            del update_data['actions']
        
        # Update all other fields
        current_rule.update(update_data)
        
        # Send the update
        response = self.session.put(
            f"{self.base_url}/rest/rules/{rule.uid}",
            json=current_rule
        )
        
        response.raise_for_status()
        return self.get_rule(rule.uid)

    def update_rule_script_action(
        self, rule_uid: str, action_id: str, script_type: str, script_content: str
    ) -> Dict[str, Any]:
        """
        Update a script action in a rule
        
        Args:
            rule_uid: UID of the rule to update
            action_id: ID of the action to update
            script_type: Type of the script
            script_content: Content of the script
        """
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
        return self.update_rule(RuleUpdate(uid=rule_uid, actions=[action_update]))

    def delete_rule(self, rule_uid: str) -> bool:
        """
        Delete a rule
        
        Args:
            rule_uid: UID of the rule to delete
        
        Returns:
            bool: True if the rule was deleted, False otherwise
        """
        response = self.session.delete(f"{self.base_url}/rest/rules/{rule_uid}")
        if response.status_code == 404:
            raise ValueError(f"Rule with UID '{rule_uid}' not found")

        response.raise_for_status()
        return True

    def run_rule_now(self, rule_uid: str) -> bool:
        """
        Run a rule immediately
        
        Args:
            rule_uid: UID of the rule to run
        
        Returns:
            bool: True if the rule was run, raises an error otherwise
        
        Raises:
            ValueError: If the rule with the given UID does not exist or run fails
        """
        if not rule_uid:
            raise ValueError("Rule UID cannot be empty")

        # Send request to run the rule
        response = self.session.post(f"{self.base_url}/rest/rules/{rule_uid}/runnow")

        if response.status_code == 404:
            raise ValueError(f"Rule with UID '{rule_uid}' not found")

        response.raise_for_status()
        return True

    def set_rule_enabled(self, rule_uid: str, enabled: bool = True) -> bool:
        """
        Enable or disable a rule
        
        Args:
            rule_uid: UID of the rule to enable/disable
            enabled: Whether to enable (True) or disable (False) the rule
            
        Returns:
            bool: True if the operation was successful, raises an error otherwise
            
        Raises:
            ValueError: If the rule with the given UID does not exist or the operation fails
        """
        if not rule_uid:
            raise ValueError("Rule UID cannot be empty")
            
        # Send request to enable/disable the rule
        response = self.session.post(
            f"{self.base_url}/rest/rules/{rule_uid}/enable",
            data="true" if enabled else "false",
            headers={"Content-Type": "text/plain"}
        )

        if response.status_code == 404:
            raise ValueError(f"Rule with UID '{rule_uid}' not found")
            
        response.raise_for_status()
        return True

    # Rule Script Actions
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

    def get_script(self, script_id: str) -> Dict[str, Any]:
        """
        Get a specific script by ID. A script is a rule without a trigger and tag of 'Script'
        
        Args:
            script_id: ID of the script to retrieve
    
        Returns:
            Dict[str, Any]: The script details
        
        Raises:
            ValueError: If the script ID is invalid or the rule is not a valid script
        """
        if not script_id:
            raise ValueError("Script ID cannot be empty")

        rule = self.get_rule(script_id)
    
        # Check if it's a valid script
        if "Script" not in rule.get("tags", []):
            raise ValueError(f"Rule with ID '{script_id}' is not a script (missing 'Script' tag)")
        
        return rule

    def create_script(
        self, script_id: str, script_name: str,script_type: str, content: str
    ) -> Dict[str, Any]:
        """
        Create a new script.  A script is a rule without a trigger and tag of 'Script'
        
        Args:
            script_id: ID of the script to create
            script_name: Name of the script
            script_type: Type of the script
            content: Content of the script
        
        Returns:
            Dict[str, Any]: The created script
        
        Raises:
            ValueError: If the script ID is empty or the script type is empty
        """
        if not content:
            raise ValueError("Script content cannot be empty")
        if not script_type:
            raise ValueError("Script type cannot be empty")

        rule = RuleCreate(
            uid=script_id,
            name=script_name,
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
        self, script_id: str, script_name: str, script_type: str, content: str
    ) -> Dict[str, Any]:
        """
        Update an existing script. A script is a rule without a trigger and tag of 'Script'
        
        Args:
            script_id: ID of the script to update
            script_name: Name of the script
            script_type: Type of the script (e.g., 'application/javascript')
            content: Content of the script
    
        Returns:
            Dict[str, Any]: The updated script
        
        Raises:
            ValueError: If the script ID is invalid or the update fails
        """
        # This will validate that it's a valid script
        current_script = self.get_script(script_id)
    
        # Prepare the update
        update_data = {
            "name": script_name,
            "tags":["Script"],
            "triggers":[],
            "actions": [{
                **current_script["actions"][0],  # Keep existing action ID and other fields
                "configuration": {
                    "type": script_type,
                    "script": content
                }
            }]
        }
    
        # Send the update
        response = self.session.put(
            f"{self.base_url}/rest/rules/{script_id}",
            json=update_data
        )
        if response.status_code == 404:
            raise ValueError(f"Script with ID '{script_id}' not found")
    
        response.raise_for_status()
    
        # Return the updated script
        return self.get_script(script_id)

    def delete_script(self, script_id: str) -> bool:
        """
        Delete a script. A script is a rule without a trigger and tag of 'Script'
        
        Args:
            script_id: ID of the script to delete
    
        Returns:
            bool: True if the script was deleted successfully or raises an error
    
        Raises:
            ValueError: If the script ID is invalid or the deletion fails
        """
        return self.delete_rule(script_id)

    # ===== Tags =====
    def list_semantic_tags(
        self, parent_tag_uid: Optional[str] = None, category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all semantic tags

        Args:
            category: If provided, only return tags that belong to this category of tags (Location, Equipment, Point or Property)
            parent_tag_uid: If provided, only return tags that are a subtag of this tag

        Returns:
            List of tag dictionaries
        """
        response = self.session.get(f"{self.base_url}/rest/tags")
        response.raise_for_status()

        tags = response.json()

        if category:
            tags = [tag for tag in tags if tag['uid'].lower().startswith(category.lower())]

        if parent_tag_uid:
            tags = [tag for tag in tags 
                   if tag['uid'] and tag['uid'].lower().startswith(f"{parent_tag_uid.lower()}_")]

        return tags

    def get_semantic_tag(self, tag_uid: str, include_subtags: bool = False) -> Optional[List[Dict[str, Any]]]:
        """
        Get a specific semantic tag by uid

        Args:
            tag_uid: UID of the tag to retrieve
            include_subtags: If True, include subtags of the tag

        Returns:
            List of tag dictionaries

        Raises:
            ValueError: If the tag UID is invalid or the tag is not found
        """
        if tag_uid is None:
            return None

        response = self.session.get(f"{self.base_url}/rest/tags/{tag_uid}")
        if response.status_code == 404:
            raise ValueError(f"Tag with UID '{tag_uid}' not found")

        response.raise_for_status()
        tags = response.json()
        if not include_subtags:
            return [tag for tag in tags if tag['uid'] == tag_uid]
        return tags
    
    def create_semantic_tag(self, tag: Tag) -> Dict[str, Any]:
        """
        Create a new semantic tag

        Args:
            tag: Tag to create

        Returns:
            Dict[str, Any]: The created tag

        Raises:
            ValueError: If the tag UID is invalid or the tag already exists
        """

        try:
            if self.get_semantic_tag(tag.uid):
                raise ValueError(f"Tag with UID '{tag.uid}' already exists")
        except ValueError as e:
            pass

        payload = tag.model_dump(exclude_unset=True, by_alias=True)

        response = self.session.post(f"{self.base_url}/rest/tags", json=payload)
        if response.status_code == 400:
            raise ValueError(f"Tag with UID '{tag.uid}' is invalid or the tag label is missing")
        if response.status_code == 409:
            raise ValueError(f"Tag with UID '{tag.uid}' already exists")

        response.raise_for_status()
        return self.get_semantic_tag(tag.uid)[0]

    def delete_semantic_tag(self, tag_uid: str) -> bool:
        """
        Delete a semantic tag by uid

        Args:
            tag_uid: UID of the tag to delete

        Returns:
            bool: True if the tag was deleted successfully or raises an error

        Raises:
            ValueError: If the tag UID is invalid or the tag is not found
        """
        response = self.session.delete(f"{self.base_url}/rest/tags/{tag_uid}")
        if response.status_code == 404:
            raise ValueError(f"Tag with UID '{tag_uid}' not found")
        if response.status_code == 405:
            raise ValueError(f"Tag with UID '{tag_uid}' is not removable")
        
        response.raise_for_status()
        return True

    # Item Tags
    def add_item_semantic_tag(self, item_name: str, tag_uid: str) -> bool:
        """
        Add semantic tag to a specific item

        Args:
            item_name: Name of the item to add the tag to
            tag_uid: UID of the tag to add

        Returns:
            bool: True if the tag was added successfully or raises an error

        Raises:
            ValueError: If the item or tag is not found
        """
        if not item_name:
            raise ValueError("Item name is required")
        if not tag_uid:
            raise ValueError("Tag UID is required")

        tag = self.get_semantic_tag(tag_uid, include_subtags=False)[0]

        response = self.session.put(
            f"{self.base_url}/rest/items/{item_name}/tags/{tag['name']}"
        )
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item_name}' not found")
        if response.status_code == 405:
            raise ValueError(f"Item with name '{item_name}' is not editable")
        
        response.raise_for_status()
        return self.get_item(item_name)

    def remove_item_semantic_tag(self, item_name: str, tag_uid: str) -> bool:
        """
        Delete semantic tag for a specific item

        Args:
            item_name: Name of the item to delete the tag from
            tag_uid: UID of the tag to delete

        Returns:
            bool: True if the tag was deleted successfully or raises an error

        Raises:
            ValueError: If the item or tag is not found
        """
        if not item_name:
            raise ValueError("Item name is required")
        if not tag_uid:
            raise ValueError("Tag UID is required")

        tag = self.get_semantic_tag(tag_uid, include_subtags=False)[0]

        response = self.session.delete(
            f"{self.base_url}/rest/items/{item_name}/tags/{tag['name']}"
        )
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item_name}' not found")
        if response.status_code == 405:
            raise ValueError(f"Item with name '{item_name}' is not editable")
        
        response.raise_for_status()
        return self.get_item(item_name)

    def add_item_non_semantic_tag(self, item_name: str, tag_name: str) -> bool:
        """
        Add non-semantic tag to a specific item

        Args:
            item_name: Name of the item to add the tag to
            tag_name: Name of the tag to add

        Returns:
            bool: True if the tag was added successfully or raises an error

        Raises:
            ValueError: If the item or tag is not found
        """
        if not item_name:
            raise ValueError("Item name is required")
        if not tag_name:
            raise ValueError("Tag name is required")

        response = self.session.put(
            f"{self.base_url}/rest/items/{item_name}/tags/{tag_name}"
        )
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item_name}' not found")
        if response.status_code == 405:
            raise ValueError(f"Item with name '{item_name}' is not editable")
        
        response.raise_for_status()
        return self.get_item(item_name)

    def remove_item_non_semantic_tag(self, item_name: str, tag_name: str) -> bool:
        """
        Delete non-semantic tag for a specific item

        Args:
            item_name: Name of the item to delete the tag from
            tag_name: Name of the tag to delete

        Returns:
            bool: True if the tag was deleted successfully or raises an error

        Raises:
            ValueError: If the item or tag is not found
        """
        if not item_name:
            raise ValueError("Item name is required")
        if not tag_name:
            raise ValueError("Tag name is required")

        response = self.session.delete(
            f"{self.base_url}/rest/items/{item_name}/tags/{tag_name}"
        )
        if response.status_code == 404:
            raise ValueError(f"Item with name '{item_name}' not found")
        if response.status_code == 405:
            raise ValueError(f"Item with name '{item_name}' is not editable")

        response.raise_for_status()
        return self.get_item(item_name)
    
    def list_inbox_things(
        self,
        page: int = 1,
        page_size: int = 15,
        sort_order: str = "asc"
    ) -> Dict[str, Any]:
        """
        Get a paginated list of discovered things in the inbox
        
        Args:
            page: Page number (1-based)
            page_size: Number of items per page
            sort_order: Sort order ("asc" or "desc")
            
        Returns:
            Dictionary containing pagination info and list of inbox items
        """
        response = self.session.get(f"{self.base_url}/rest/inbox")
        response.raise_for_status()
        all_items = response.json()
        
        # Apply sorting
        reverse_sort = sort_order.lower() == "desc"
        all_items.sort(key=lambda x: x.get("label", ""), reverse=reverse_sort)
        
        # Calculate pagination
        total_items = len(all_items)
        total_pages = (total_items + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_items)
        
        paginated_items = all_items[start_idx:end_idx]
        
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
    
    def approve_inbox_thing(self,
        thing_uid: str = Field(..., description="UID of the inbox item to approve"),
        thing_id: str = Field(..., description="ID to assign to the new thing"),
        label: str = Field(..., description="Label for the new thing"),
    ) -> bool:
        """
        Approve and create a thing from an inbox item
        
        Args:
            thing_uid: UID of the inbox item
            thing_id: ID to assign to the new thing
            label: Label for the new thing
        
        Returns:
            bool: True if the thing was approved successfully or raises an error
            
        Raises:
            ValueError: If the approval fails
        """
        response = self.session.post(
            f"{self.base_url}/rest/inbox/{thing_uid}/approve?newThingId={thing_id}",
            data=label,
            headers={"Content-Type": "text/plain"}
        )
        if response.status_code == 400:
            raise ValueError(f"Thing ID {thing_id} is invalid")
        if response.status_code == 404:
            raise ValueError(f"Thing with UID '{thing_uid}' not found")
        if response.status_code == 409:
            raise ValueError(f"No binding found that supports this thing with UID '{thing_uid}'")
        response.raise_for_status()
        return True
    
    def ignore_inbox_thing(
        self,
        thing_uid: str = Field(..., description="UID of the inbox item to ignore")
    ) -> bool:
        """
        Mark an inbox item as ignored
        
        Args:
            thing_uid: UID of the inbox item to ignore
        
        Returns:
            bool: True if successful
            
        Raises:
            ValueError: If the operation fails
        """
        response = self.session.post(f"{self.base_url}/rest/inbox/{thing_uid}/ignore")
        response.raise_for_status()
        return True
    
    def unignore_inbox_thing(
        self,
        thing_uid: str = Field(..., description="UID of the inbox item to unignore")
    ) -> bool:
        """
        Remove ignore status from an inbox item
        
        Args:
            thing_uid: UID of the inbox item to unignore
        
        Returns:
            bool: True if successful
            
        Raises:
            ValueError: If the operation fails
        """
        response = self.session.post(f"{self.base_url}/rest/inbox/{thing_uid}/unignore")
        response.raise_for_status()
        return True
    
    def delete_inbox_thing(
        self,
        thing_uid: str = Field(..., description="UID of the inbox item to delete")
    ) -> bool:
        """
        Delete an item from the inbox
        
        Args:
            thing_uid: UID of the inbox item to delete
        
        Returns:
            bool: True if successful
            
        Raises:
            ValueError: If the deletion fails
        """
        response = self.session.delete(f"{self.base_url}/rest/inbox/{thing_uid}")
        if response.status_code == 404:
            raise ValueError(f"Thing with UID '{thing_uid}' not found in inbox")
        response.raise_for_status()
        return True

    # Helper methods
    def _enhance_tags(self, tags: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for tag in tags:
            if 'uid' in tag and '_' in tag['uid']:
                tag['parentuid'] = tag['uid'].rsplit('_', 1)[0]
        
            if 'uid' in tag and '_' in tag['uid']:
                tag['category'] = tag['uid'].split('_')[0]
        return tags
        
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
        
        if not output_fields or (member_tags and output_fields and ("semanticTags" in output_fields or "nonSemanticTags" in output_fields)):
            semantic_tags = [tag for tag in tags if tag.get('name') in member_tags]
            semantic_tags = self._enhance_tags(semantic_tags)
            non_semantic_tags = [tag for tag in member_tags if tag not in [t.get('name', '') for t in tags]]
            
            if output_fields is None:
                member["semanticTags"] = semantic_tags
                member["nonSemanticTags"] = non_semantic_tags
            else:
                if "semanticTags" in output_fields:
                    member["semanticTags"] = semantic_tags
                if "nonSemanticTags" in output_fields:
                    member["nonSemanticTags"] = non_semantic_tags
        
        # Rest of the method remains the same
        if "tags" in member:
            del member["tags"]
        
        # Help to understand that semantics metadata isn't directly editable
        for namespace, metadata in member.get("metadata", {}).items():
            if namespace == "semantics":
                metadata["editable"] = False
            else:
                metadata["editable"] = True
            
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