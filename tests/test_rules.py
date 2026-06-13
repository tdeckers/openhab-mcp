import copy
import json
import re
import unittest
import requests
from unittest.mock import MagicMock
from openhab_mcp.openhab_client import OpenHABClient
from openhab_mcp.models import RuleCreate, RuleUpdate


# ── Fixtures ──────────────────────────────────────────────────────────────────

RULE = {
    "uid": "test_rule_basicrule",
    "name": "TestRule_BasicRule",
    "description": "Test rule BasicRule",
    "tags": ["TestTag"],
    "status": {"status": "IDLE", "statusDetail": "NONE"},
    "triggers": [{"id": "1", "type": "core.ItemStateChangeTrigger",
                  "configuration": {"itemName": "Test_Item", "state": "ON"}}],
    "actions": [{"id": "2", "type": "script.ScriptAction",
                 "configuration": {"type": "text/plain", "script": "print('Test rule executed')"}}],
    "conditions": [],
    "configuration": {},
    "editable": True,
}

SCRIPT = {
    "uid": "test_script",
    "name": "TestRule_TestScript",
    "tags": ["Script"],
    "actions": [{"id": "1", "type": "script.ScriptAction",
                 "configuration": {"type": "application/javascript",
                                   "script": "console.log('Hello from test script');"}}],
    "triggers": [], "conditions": [], "configuration": {}, "editable": True,
}


# ── Helper ─────────────────────────────────────────────────────────────────────

def resp(data=None, status_code=200):
    m = MagicMock()
    m.status_code = status_code
    m.ok = status_code < 400
    m.json.return_value = copy.deepcopy(data) if data is not None else {}
    m.text = json.dumps(data) if data is not None else "[]"
    if status_code >= 400:
        m.raise_for_status.side_effect = requests.HTTPError(response=m)
    return m


# ── Base test class with URL-dispatch ─────────────────────────────────────────

class RulesTestBase(unittest.TestCase):
    def setUp(self):
        self.client = OpenHABClient(base_url="http://test.local", api_token="test-token")
        self.session = MagicMock()
        self.client.session = self.session
        self.session.delete.return_value = resp(None, 200)
        self._rules_by_uid: dict = {}
        self._setup_dispatch()

    def _setup_dispatch(self):
        def get_dispatch(url, **kwargs):
            # GET /rest/rules/{uid} — single rule
            if re.search(r'/rest/rules/[^/]+$', url):
                uid = url.rstrip('/').split('/')[-1]
                rule = self._rules_by_uid.get(uid)
                if rule is None:
                    return resp(None, 404)
                return resp(copy.deepcopy(rule))
            # GET /rest/rules — list (list_rules uses .text)
            if '/rest/rules' in url:
                tag_filter = (kwargs.get('params') or {}).get('tags')
                rules = list(self._rules_by_uid.values())
                if tag_filter:
                    rules = [r for r in rules if tag_filter in r.get('tags', [])]
                return resp(copy.deepcopy(rules))
            return resp(None, 404)

        def post_dispatch(url, **kwargs):
            # POST /rest/rules/{uid}/enable — set_rule_enabled
            if re.search(r'/rest/rules/[^/]+/enable$', url):
                uid = url.rstrip('/').split('/')[-2]
                enabled = (kwargs.get('data') or '') == 'true'
                if uid in self._rules_by_uid:
                    rule = self._rules_by_uid[uid]
                    if enabled:
                        rule['status'] = {'status': 'IDLE', 'statusDetail': 'NONE'}
                    else:
                        rule['status'] = {'status': 'UNINITIALIZED', 'statusDetail': 'DISABLED'}
                return resp(None, 200)
            # POST /rest/rules — create rule
            if '/rest/rules' in url:
                return resp(None, 201)
            return resp(None, 404)

        def put_dispatch(url, **kwargs):
            # PUT /rest/rules/{uid} — update rule
            if re.search(r'/rest/rules/[^/]+$', url):
                uid = url.rstrip('/').split('/')[-1]
                if uid in self._rules_by_uid and kwargs.get('json'):
                    self._rules_by_uid[uid].update(kwargs['json'])
                return resp(None, 200)
            return resp(None, 404)

        self.session.get.side_effect = get_dispatch
        self.session.post.side_effect = post_dispatch
        self.session.put.side_effect = put_dispatch

    def _register(self, *rules):
        for rule in rules:
            self._rules_by_uid[rule['uid']] = copy.deepcopy(rule)

    def _make_rule(self, name_suffix="BasicRule", uid=None, **overrides):
        r = copy.deepcopy(RULE)
        r["uid"] = uid or f"test_rule_{name_suffix.lower()}"
        r["name"] = f"TestRule_{name_suffix}"
        r["description"] = f"Test rule {name_suffix}"
        r.update(overrides)
        return r


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestOpenHABRules(RulesTestBase):

    def test_create_and_delete_rule(self):
        rule = self._make_rule()
        self._register(rule)

        created = self.client.create_rule(RuleCreate(
            uid="test_rule_basicrule", name="TestRule_BasicRule",
            description="Test rule BasicRule", tags=["TestTag"],
            triggers=[{"id": "1", "type": "core.ItemStateChangeTrigger",
                       "configuration": {"itemName": "Test_Item", "state": "ON"}}],
            actions=[{"id": "2", "type": "script.ScriptAction",
                      "configuration": {"type": "text/plain", "script": "print('Test rule executed')"}}]
        ))
        self.assertEqual(created["name"], "TestRule_BasicRule")
        self.assertEqual(created["description"], "Test rule BasicRule")

        rules = self.client.list_rules(filter_tag="TestTag")["rules"]
        self.assertIn("TestRule_BasicRule", [r["name"] for r in rules])

        del self._rules_by_uid["test_rule_basicrule"]
        deleted = self.client.delete_rule(created["uid"])
        self.assertTrue(deleted)

        rules_after = self.client.list_rules(filter_tag="TestTag")["rules"]
        self.assertNotIn("TestRule_BasicRule", [r["name"] for r in rules_after])

    def test_get_rule(self):
        rule = self._make_rule("GetRuleTest", uid="test_rule_getruletest")
        self._register(rule)

        created = self.client.create_rule(RuleCreate(
            uid="test_rule_getruletest", name="TestRule_GetRuleTest",
            description="Test rule GetRuleTest", tags=["TestTag"],
            triggers=[{"id": "1", "type": "core.ItemStateChangeTrigger", "configuration": {"itemName": "Test_Item", "state": "ON"}}],
            actions=[{"id": "2", "type": "script.ScriptAction", "configuration": {"type": "text/plain", "script": "print('test')"}}]
        ))
        retrieved = self.client.get_rule(created["uid"])
        self.assertEqual(retrieved["uid"], "test_rule_getruletest")
        self.assertEqual(retrieved["name"], "TestRule_GetRuleTest")

    def test_update_rule(self):
        rule = self._make_rule("UpdateRuleTest", uid="test_rule_updateruletest")
        self._register(rule)

        created = self.client.create_rule(RuleCreate(
            uid="test_rule_updateruletest", name="TestRule_UpdateRuleTest",
            description="Test rule UpdateRuleTest", tags=["TestTag"],
            triggers=[{"id": "1", "type": "core.ItemStateChangeTrigger", "configuration": {"itemName": "Test_Item", "state": "ON"}}],
            actions=[{"id": "2", "type": "script.ScriptAction", "configuration": {"type": "text/plain", "script": "print('test')"}}]
        ))
        # Patch the stored rule to reflect the update result
        self._rules_by_uid["test_rule_updateruletest"]["description"] = "Updated description"
        self._rules_by_uid["test_rule_updateruletest"]["tags"] = ["TestTag", "UpdatedTag"]

        result = self.client.update_rule(RuleUpdate(
            uid=created["uid"], description="Updated description", tags=["TestTag", "UpdatedTag"]
        ))
        self.assertEqual(result["description"], "Updated description")
        self.assertIn("UpdatedTag", result["tags"])

    def test_run_rule(self):
        rule = self._make_rule("RunRuleTest", uid="test_run_rule")
        self._register(rule)

        created = self.client.create_rule(RuleCreate(
            uid="test_run_rule", name="TestRule_RunRuleTest",
            description="Test rule for running manually", tags=["TestTag"],
            triggers=[{"id": "1", "type": "core.ItemStateChangeTrigger", "configuration": {"itemName": "Test_Item", "state": "ON"}}],
            actions=[{"id": "2", "type": "script.ScriptAction", "configuration": {"type": "text/plain", "script": "print('test')"}}]
        ))
        result = self.client.run_rule_now(created["uid"])
        self.assertTrue(result)

    def test_enable_disable_rule(self):
        rule = self._make_rule("EnableDisableTest", uid="test_rule_enabledisabletest")
        self._register(rule)

        created = self.client.create_rule(RuleCreate(
            uid="test_rule_enabledisabletest", name="TestRule_EnableDisableTest",
            description="Test rule EnableDisableTest", tags=["TestTag"],
            triggers=[{"id": "1", "type": "core.ItemStateChangeTrigger", "configuration": {"itemName": "Test_Item", "state": "ON"}}],
            actions=[{"id": "2", "type": "script.ScriptAction", "configuration": {"type": "text/plain", "script": "print('test')"}}]
        ))

        self.client.set_rule_enabled(created["uid"], False)
        rule_after_disable = self.client.get_rule(created["uid"])
        self.assertEqual(rule_after_disable["status"]["status"], "UNINITIALIZED")

        self.client.set_rule_enabled(created["uid"], True)
        rule_after_enable = self.client.get_rule(created["uid"])
        self.assertEqual(rule_after_enable["status"]["status"], "IDLE")

    def test_script_operations(self):
        self._register(SCRIPT)

        created = self.client.create_script("test_script", "TestRule_TestScript", "application/javascript", "console.log('Hello from test script');")
        self.assertEqual(created["uid"], "test_script")
        self.assertIn("Script", created["tags"])

        retrieved = self.client.get_script("test_script")
        self.assertEqual(retrieved["uid"], "test_script")

        updated = self.client.update_script("test_script", "TestRule_TestScript", "application/javascript", "console.log('Updated script content');")
        self.assertEqual(updated["actions"][0]["configuration"]["script"], "console.log('Updated script content');")

        self.client.delete_script("test_script")

    def test_comprehensive_rule_updates(self):
        base_rule = self._make_rule("ComprehensiveUpdateTest", uid="test_comprehensive_update")
        self._register(base_rule)

        created = self.client.create_rule(RuleCreate(
            uid="test_comprehensive_update", name="TestRule_ComprehensiveUpdateTest",
            description="Test rule for comprehensive updates", tags=["TestTag"],
            triggers=[{"id": "trigger1", "type": "core.ItemStateChangeTrigger", "configuration": {"itemName": "Test_Item", "state": "ON"}}],
            actions=[{"id": "action1", "type": "script.ScriptAction", "configuration": {"type": "text/plain", "script": "console.log('Initial action');"}}]
        ))
        rule_uid = created["uid"]

        # Add a second action
        self._rules_by_uid[rule_uid]["actions"] = [
            {"id": "action1", "type": "script.ScriptAction", "configuration": {"type": "text/plain", "script": "console.log('Initial action');"}},
            {"id": "action2", "type": "script.ScriptAction", "configuration": {"type": "application/javascript", "script": "items.getItem('Test_Item').sendCommand('OFF');"}},
        ]
        updated = self.client.update_rule(RuleUpdate(uid=rule_uid, actions=[
            {"id": "action1", "type": "script.ScriptAction", "configuration": {"type": "text/plain", "script": "console.log('Initial action');"}},
            {"id": "action2", "type": "script.ScriptAction", "configuration": {"type": "application/javascript", "script": "items.getItem('Test_Item').sendCommand('OFF');"}},
        ]))
        self.assertEqual(len(updated["actions"]), 2)
        self.assertIn("action1", [a["id"] for a in updated["actions"]])
        self.assertIn("action2", [a["id"] for a in updated["actions"]])

        # Update action1's script
        self._rules_by_uid[rule_uid]["actions"][0]["configuration"]["script"] = "console.log('Updated initial action');"
        updated = self.client.update_rule(RuleUpdate(uid=rule_uid, actions=[
            {"id": "action1", "type": "script.ScriptAction", "configuration": {"type": "text/plain", "script": "console.log('Updated initial action');"}},
            {"id": "action2", "type": "script.ScriptAction", "configuration": {"type": "application/javascript", "script": "items.getItem('Test_Item').sendCommand('OFF');"}},
        ]))
        action1 = next(a for a in updated["actions"] if a["id"] == "action1")
        self.assertIn("Updated initial action", action1["configuration"]["script"])

        # Replace action2 with action3
        self._rules_by_uid[rule_uid]["actions"] = [
            {"id": "action1", "type": "script.ScriptAction", "configuration": {"type": "text/plain", "script": "console.log('Updated initial action');"}},
            {"id": "action3", "type": "script.ScriptAction", "configuration": {"type": "application/javascript", "script": "console.log('Third action added');"}},
        ]
        updated = self.client.update_rule(RuleUpdate(uid=rule_uid, actions=[
            {"id": "action1", "type": "script.ScriptAction", "configuration": {"type": "text/plain", "script": "console.log('Updated initial action');"}},
            {"id": "action3", "type": "script.ScriptAction", "configuration": {"type": "application/javascript", "script": "console.log('Third action added');"}},
        ]))
        self.assertEqual(len(updated["actions"]), 2)
        self.assertNotIn("action2", [a["id"] for a in updated["actions"]])

        # Full update
        self._rules_by_uid[rule_uid].update({
            "description": "Fully updated rule",
            "tags": ["TestTag", "UpdatedTag", "FinalTag"],
            "configuration": {"customConfig": "value123", "anotherConfig": 42},
            "actions": [
                {"id": "action1", "type": "script.ScriptAction", "configuration": {"type": "text/plain", "script": "console.log('Final update to action1');"}},
                {"id": "action4", "type": "script.ScriptAction", "configuration": {"type": "application/javascript", "script": "console.log('Fourth action with different content');"}},
            ],
        })
        updated = self.client.update_rule(RuleUpdate(
            uid=rule_uid, description="Fully updated rule",
            tags=["TestTag", "UpdatedTag", "FinalTag"],
            configuration={"customConfig": "value123", "anotherConfig": 42},
            actions=[
                {"id": "action1", "type": "script.ScriptAction", "configuration": {"type": "text/plain", "script": "console.log('Final update to action1');"}},
                {"id": "action4", "type": "script.ScriptAction", "configuration": {"type": "application/javascript", "script": "console.log('Fourth action with different content');"}},
            ]
        ))
        self.assertEqual(updated["description"], "Fully updated rule")
        self.assertEqual(set(updated["tags"]), {"TestTag", "UpdatedTag", "FinalTag"})
        self.assertEqual(updated["configuration"]["customConfig"], "value123")
        self.assertEqual(updated["configuration"]["anotherConfig"], 42)
        self.assertEqual(len(updated["actions"]), 2)
        action1 = next(a for a in updated["actions"] if a["id"] == "action1")
        self.assertIn("Final update to action1", action1["configuration"]["script"])


if __name__ == "__main__":
    unittest.main()
