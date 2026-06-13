import copy
import json
import re
import unittest
import requests
from unittest.mock import MagicMock
from openhab_mcp.openhab_client import OpenHABClient
from openhab_mcp.models import ItemCreate, ItemMetadata, Tag, ItemUpdate


# ── Fixtures ──────────────────────────────────────────────────────────────────

SEMANTIC_TAGS = [
    {"uid": "Equipment_Lighting", "name": "Lighting", "category": "Equipment", "editable": True, "synonyms": []},
    {"uid": "Point_Control_Switch", "name": "Switch", "category": "Point", "editable": False, "synonyms": []},
    {"uid": "Property_Light", "name": "Light", "category": "Property", "editable": False, "synonyms": []},
    {"uid": "Location_TestBuilding", "name": "TestBuilding", "category": "Location", "editable": True, "synonyms": []},
    {"uid": "Location_TestBuilding_TestRoom", "name": "TestRoom", "category": "Location",
     "parentuid": "Location_TestBuilding", "editable": True, "synonyms": []},
    {"uid": "Equipment_TestDevice", "name": "TestDevice", "category": "Equipment", "editable": True, "synonyms": []},
]

SWITCH_ITEM = {
    "name": "TestItem_Switch1", "type": "Switch", "label": "Test Switch1",
    "state": "NULL", "groupNames": [], "tags": [], "metadata": {},
    "semanticTags": [], "nonSemanticTags": [], "editable": True,
}

DIMMER_ITEM = {
    "name": "TestItem_Dimmer1", "type": "Dimmer", "label": "Test Dimmer1",
    "state": "NULL", "groupNames": [], "tags": [], "metadata": {},
    "semanticTags": [], "nonSemanticTags": [], "editable": True,
}

GROUP_ITEM = {
    "name": "TestItem_Group_TestGroup", "type": "Group", "label": "Test Group TestGroup",
    "state": "NULL", "groupNames": [], "members": [], "tags": [], "metadata": {},
    "semanticTags": [], "nonSemanticTags": [], "editable": True,
}

FULL_ITEM = {
    "name": "TestItem_FullItem", "type": "Dimmer", "label": "Test Full Dimmer Item",
    "category": "Light", "state": "NULL", "groupNames": ["TestItem_TestGroup"],
    "tags": ["Lighting", "TestTag", "Dimmable"],
    "metadata": {
        "commandDescription": {"value": " ", "config": {"options": "ON=Switch ON, OFF=Switch OFF, INCREASE=Increase, DECREASE=Decrease"}, "editable": True},
        "stateDescription": {"value": " ", "config": {"minimum": 0, "maximum": 100, "step": 5, "pattern": "%d%%", "readOnly": False, "options": "0=Off, 100=Full"}, "editable": True},
        "unit": {"value": "%", "config": {}, "editable": True},
    },
    "semanticTags": [{"uid": "Equipment_Lighting", "name": "Lighting", "category": "Equipment", "editable": True}],
    "nonSemanticTags": ["TestTag", "Dimmable"],
    "editable": True,
}


# ── Helper ─────────────────────────────────────────────────────────────────────

def resp(data=None, status_code=200):
    """Build a mock requests.Response."""
    m = MagicMock()
    m.status_code = status_code
    m.ok = status_code < 400
    m.json.return_value = data if data is not None else {}
    m.text = json.dumps(data) if data is not None else "{}"
    if status_code >= 400:
        m.raise_for_status.side_effect = requests.HTTPError(response=m)
    return m


# ── Base test class with URL-dispatch ─────────────────────────────────────────

class ItemsTestBase(unittest.TestCase):
    def setUp(self):
        self.client = OpenHABClient(base_url="http://test.local", api_token="test-token")
        self.session = MagicMock()
        self.client.session = self.session
        # Default: all mutations succeed, GET dispatches by URL
        self.session.put.return_value = resp(None, 200)
        self.session.post.return_value = resp(None, 201)
        self.session.delete.return_value = resp(None, 200)
        self._items_by_name: dict = {}  # name → item dict
        self._setup_get_dispatch()

    def _setup_get_dispatch(self):
        """Route GET calls by URL pattern. Tests update self._items_by_name to control list_items results."""
        tags = SEMANTIC_TAGS

        def dispatch(url, **kwargs):
            # /rest/tags/{uid} — return tag list for that UID (+ subtags in SEMANTIC_TAGS)
            if re.search(r'/rest/tags/[^/]+$', url):
                uid = url.rstrip('/').split('/')[-1]
                return resp([t for t in tags if t['uid'] == uid or t.get('parentuid') == uid])
            # /rest/tags — full list
            if '/rest/tags' in url:
                parent = (kwargs.get('params') or {}).get('prefix') or (kwargs.get('params') or {}).get('parentTagUID')
                if parent:
                    return resp([t for t in tags if t.get('parentuid') == parent or t['uid'] == parent])
                category = (kwargs.get('params') or {}).get('category')
                if category:
                    return resp([t for t in tags if t.get('category') == category])
                return resp(tags)
            # /rest/items/{name}/members — group members
            if re.search(r'/rest/items/[^/]+/members$', url):
                return resp(copy.deepcopy(list(self._items_by_name.values())))
            # /rest/items — item list, optionally filtered by name
            if '/rest/items' in url:
                name_filter = (kwargs.get('params') or {}).get('name')
                if name_filter:
                    return resp(copy.deepcopy([i for i in self._items_by_name.values() if name_filter.lower() in i['name'].lower()]))
                return resp(copy.deepcopy(list(self._items_by_name.values())))
            return resp({}, 404)

        self.session.get.side_effect = dispatch

    def _register(self, *items):
        """Register items so list_items / get_item can find them."""
        for item in items:
            self._items_by_name[item['name']] = item


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestOpenHABItems(ItemsTestBase):

    def test_create_and_delete_item(self):
        self._register(SWITCH_ITEM)

        created = self.client.create_item(ItemCreate(name="TestItem_Switch1", type="Switch", label="Test Switch1"))
        self.assertEqual(created["name"], "TestItem_Switch1")
        self.assertEqual(created["type"], "Switch")

        items = self.client.list_items(filter_name="TestItem_Switch1")["items"]
        self.assertEqual(len(items), 1)

        self.session.delete.return_value = resp(None, 200)
        deleted = self.client.delete_item("TestItem_Switch1")
        self.assertTrue(deleted)

        self._items_by_name.clear()
        items_after = self.client.list_items(filter_name="TestItem_Switch1")["items"]
        self.assertEqual(len(items_after), 0)

    def test_update_item_metadata(self):
        item_with_meta = dict(DIMMER_ITEM, metadata={"test_namespace": {"value": "test_value", "config": {"key1": "value1"}, "editable": True}})
        self._register(item_with_meta)

        updated = self.client.add_or_update_item_metadata(
            "TestItem_Dimmer1", "test_namespace",
            ItemMetadata(value="test_value", config={"key1": "value1", "key2": "value2"})
        )
        self.assertIn("metadata", updated)
        self.assertIn("test_namespace", updated["metadata"])
        self.assertEqual(updated["metadata"]["test_namespace"]["value"], "test_value")

    def test_group_item_operations(self):
        item1 = dict(SWITCH_ITEM)
        item2 = dict(DIMMER_ITEM)
        item3 = {"name": "TestItem_String1", "type": "String", "state": "NULL",
                 "groupNames": [], "tags": [], "metadata": {}, "semanticTags": [], "nonSemanticTags": [], "editable": True}

        group_2 = dict(GROUP_ITEM, members=[item1, item2])
        group_3 = dict(GROUP_ITEM, members=[item1, item2, item3])
        group_no_1 = dict(GROUP_ITEM, members=[item2, item3])
        self._register(group_2)  # add_item_member returns get_item(group)

        # add_item_member calls PUT then get_item(group_name) → list_items → filters by name
        # We need get_item("TestItem_Group_TestGroup") to return the group
        self._items_by_name["TestItem_Group_TestGroup"] = group_2
        group = self.client.add_item_member("TestItem_Group_TestGroup", "TestItem_Switch1")
        self.assertEqual(len(group["members"]), 2)

        self._items_by_name["TestItem_Group_TestGroup"] = group_3
        group = self.client.add_item_member("TestItem_Group_TestGroup", "TestItem_String1")
        self.assertEqual(len(group["members"]), 3)

        self._items_by_name["TestItem_Group_TestGroup"] = group_no_1
        group = self.client.remove_item_member("TestItem_Group_TestGroup", "TestItem_Switch1")
        self.assertEqual(len(group["members"]), 2)
        self.assertNotIn("TestItem_Switch1", [m["name"] for m in group["members"]])

    def test_item_state_operations(self):
        self._register(dict(SWITCH_ITEM, state="ON"))
        self.client.update_item_state("TestItem_Switch1", "ON")
        updated = self.client.get_item("TestItem_Switch1")
        self.assertEqual(updated["state"], "ON")

        self._register(dict(DIMMER_ITEM, state="50"))
        self.client.update_item_state("TestItem_Dimmer1", "50")
        updated_dimmer = self.client.get_item("TestItem_Dimmer1")
        self.assertEqual(updated_dimmer["state"], "50")

    def test_tag_operations(self):
        new_tag = {"uid": "Location_TestLocation", "name": "TestLocation",
                   "label": "Test Location", "description": "A test location tag",
                   "category": "Location", "synonyms": [], "editable": True}
        all_tags_with_new = SEMANTIC_TAGS + [new_tag]

        # Set up dispatch including the new tag before create (needed by create_semantic_tag's get call)
        def dispatch_with_new(url, **kwargs):
            if re.search(r'/rest/tags/[^/]+$', url):
                uid = url.rstrip('/').split('/')[-1]
                return resp([t for t in all_tags_with_new if t['uid'] == uid])
            if '/rest/tags' in url:
                category = (kwargs.get('params') or {}).get('category')
                if category:
                    return resp([t for t in all_tags_with_new if t.get('category') == category])
                return resp(all_tags_with_new)
            if '/rest/items' in url:
                return resp(copy.deepcopy(list(self._items_by_name.values())))
            return resp({}, 404)
        self.session.get.side_effect = dispatch_with_new

        self.session.post.return_value = resp(new_tag, 201)
        created = self.client.create_semantic_tag(Tag(
            uid="Location_TestLocation", name="TestLocation",
            label="Test Location", category="Location", description="A test location tag"
        ))
        self.assertEqual(created["uid"], "Location_TestLocation")

        retrieved = self.client.get_semantic_tag("Location_TestLocation")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved[0]["uid"], "Location_TestLocation")

        all_tags = self.client.list_semantic_tags()
        self.assertTrue(any(t["uid"] == "Location_TestLocation" for t in all_tags))

        loc_tags = self.client.list_semantic_tags(category="Location")
        self.assertTrue(any(t["uid"] == "Location_TestLocation" for t in loc_tags))

        self.client.delete_semantic_tag("Location_TestLocation")

        # After delete: tag no longer found
        def dispatch_not_found(url, **kwargs):
            if re.search(r'/rest/tags/Location_TestLocation$', url):
                return resp([], 404)
            return dispatch_with_new(url, **kwargs)
        self.session.get.side_effect = dispatch_not_found
        with self.assertRaises(ValueError):
            self.client.get_semantic_tag("Location_TestLocation")

    def test_item_tag_operations(self):
        self._register(SWITCH_ITEM)
        self.session.post.return_value = resp(
            {"uid": "Equipment_TestDevice", "name": "TestDevice", "label": "Test Device",
             "category": "Equipment", "synonyms": [], "editable": True}, 201
        )
        self.session.put.return_value = resp(None, 200)
        self.session.delete.return_value = resp(None, 200)

        created_tag = self.client.create_semantic_tag(Tag(uid="Equipment_TestDevice", name="TestDevice", label="Test Device", category="Equipment"))

        # add_item_semantic_tag: calls get_semantic_tag(uid) → GET /rest/tags/{uid}, then PUT, returns True
        result = self.client.add_item_semantic_tag("TestItem_Switch1", created_tag["uid"])
        self.assertTrue(result)

        # add_item_non_semantic_tag: PUT, returns True
        result = self.client.add_item_non_semantic_tag("TestItem_Switch1", "TestTag")
        self.assertTrue(result)

        # remove_item_semantic_tag: GET /rest/tags/{uid}, DELETE, returns True
        result = self.client.remove_item_semantic_tag("TestItem_Switch1", created_tag["uid"])
        self.assertTrue(result)

        # remove_item_non_semantic_tag: DELETE, returns True
        result = self.client.remove_item_non_semantic_tag("TestItem_Switch1", "TestTag")
        self.assertTrue(result)

    def test_hierarchical_tags(self):
        parent_tag = {"uid": "Location_TestBuilding", "name": "TestBuilding",
                      "label": "Test Building", "category": "Location", "synonyms": [], "editable": True}
        child_tag = {"uid": "Location_TestBuilding_TestRoom", "name": "TestRoom",
                     "label": "Test Room", "category": "Location",
                     "parentuid": "Location_TestBuilding", "synonyms": [], "editable": True}

        self.session.post.side_effect = [resp(parent_tag, 201), resp(child_tag, 201)]

        self.client.create_semantic_tag(Tag(uid="Location_TestBuilding", name="TestBuilding", label="Test Building", category="Location"))
        self.client.create_semantic_tag(Tag(uid="Location_TestBuilding_TestRoom", name="TestRoom", label="Test Room", category="Location", parentuid="Location_TestBuilding"))

        # get_semantic_tag with include_subtags=True → GET /rest/tags/Location_TestBuilding
        # dispatcher returns tag + children (by parentuid)
        subtags = self.client.get_semantic_tag("Location_TestBuilding", include_subtags=True)
        self.assertEqual(len(subtags), 2)
        uids = {t["uid"] for t in subtags}
        self.assertIn("Location_TestBuilding", uids)
        self.assertIn("Location_TestBuilding_TestRoom", uids)

        children = self.client.list_semantic_tags(parent_tag_uid="Location_TestBuilding")
        self.assertTrue(any(t["uid"] == "Location_TestBuilding_TestRoom" for t in children))

    def test_create_item_with_all_fields(self):
        group = {"name": "TestItem_TestGroup", "type": "Group", "label": "Test Group",
                 "groupType": "Dimmer", "function": {"name": "AVG"}, "state": "NULL",
                 "groupNames": [], "members": [], "tags": [], "metadata": {},
                 "semanticTags": [], "nonSemanticTags": [], "editable": True}
        self._register(group, FULL_ITEM)

        self.client.create_item(ItemCreate(
            name="TestItem_TestGroup", type="Group", label="Test Group",
            groupType="Dimmer", function={"name": "AVG"}
        ))
        created = self.client.create_item(ItemCreate(
            name="TestItem_FullItem", type="Dimmer", label="Test Full Dimmer Item",
            category="Light", groupNames=["TestItem_TestGroup"],
            semanticTags=["Equipment_Lighting"], nonSemanticTags=["TestTag", "Dimmable"],
            metadata={
                "commandDescription": ItemMetadata(value=" ", config={"options": "ON=Switch ON, OFF=Switch OFF, INCREASE=Increase, DECREASE=Decrease"}),
                "stateDescription": ItemMetadata(value=" ", config={"minimum": 0, "maximum": 100, "step": 5, "pattern": "%d%%", "readOnly": False, "options": "0=Off, 100=Full"}),
                "unit": ItemMetadata(value="%"),
            }
        ))

        self.assertEqual(created["name"], "TestItem_FullItem")
        self.assertEqual(created["label"], "Test Full Dimmer Item")
        self.assertEqual(created["category"], "Light")
        self.assertIn("TestItem_TestGroup", created["groupNames"])
        self.assertIn("TestTag", created["nonSemanticTags"])
        self.assertEqual(created["semanticTags"][0]["uid"], "Equipment_Lighting")
        self.assertEqual(created["metadata"]["commandDescription"]["config"]["options"],
                         "ON=Switch ON, OFF=Switch OFF, INCREASE=Increase, DECREASE=Decrease")
        self.assertEqual(created["metadata"]["stateDescription"]["config"]["minimum"], 0)
        self.assertEqual(created["metadata"]["unit"]["value"], "%")

        fetched_group = self.client.get_item("TestItem_TestGroup")
        self.assertEqual(fetched_group["groupType"], "Dimmer")
        self.assertEqual(fetched_group["function"]["name"], "AVG")

    def test_update_item_with_none_or_empty_values(self):
        initial = dict(DIMMER_ITEM,
            label="Test Item for Update", category="Light",
            groupNames=["TestItem_TestGroupForUpdate"],
            semanticTags=[{"uid": "Equipment_Lighting", "name": "Lighting", "category": "Equipment", "editable": True}],
            nonSemanticTags=["TestTag", "Dimmable"],
            metadata={"stateDescription": {"value": " ", "config": {"pattern": "%d%%"}, "editable": True}},
        )
        stripped = dict(DIMMER_ITEM, label=None, category=None, groupNames=[], semanticTags=[], nonSemanticTags=[])
        group_item = {"name": "TestItem_TestGroupForUpdate", "type": "Group", "label": "Test Group For Update",
                      "state": "NULL", "groupNames": [], "members": [initial], "tags": [], "metadata": {},
                      "semanticTags": [], "nonSemanticTags": [], "editable": True}
        self._register(initial, group_item)

        self._items_by_name[DIMMER_ITEM["name"]] = stripped
        self.client.remove_item_metadata("TestItem_Dimmer1", "stateDescription")
        self._items_by_name["TestItem_TestGroupForUpdate"] = dict(group_item, members=[])
        self.client.remove_item_member("TestItem_TestGroupForUpdate", "TestItem_Dimmer1")

        # update_item: PUT then get_item
        self.session.put.return_value = resp(None, 200)
        updated = self.client.update_item(ItemUpdate(
            name="TestItem_Dimmer1", type="Dimmer",
            label=None, category=None, nonSemanticTags=[], semanticTags=[]
        ))

        self.assertIsNone(updated.get("label"))
        self.assertIsNone(updated.get("category"))
        self.assertEqual(updated.get("nonSemanticTags", []), [])
        self.assertEqual(updated.get("semanticTags", []), [])
        self.assertEqual(updated.get("groupNames", []), [])

    def test_list_items_filter_group(self):
        members = [SWITCH_ITEM, DIMMER_ITEM]
        # Patch dispatcher so /members endpoint returns our list
        self._items_by_name.update({i["name"]: i for i in members})

        result = self.client.list_items(filter_group="Indoor_Room_Bedroom")
        self.assertEqual(len(result["items"]), 2)
        names = [i["name"] for i in result["items"]]
        self.assertIn("TestItem_Switch1", names)
        self.assertIn("TestItem_Dimmer1", names)

        # Verify the correct endpoint was called
        called_urls = [str(call[0][0]) for call in self.session.get.call_args_list]
        self.assertTrue(any('/members' in u for u in called_urls))
        self.assertTrue(any('Indoor_Room_Bedroom' in u for u in called_urls))


if __name__ == "__main__":
    unittest.main()
