from models import Item, ItemMetadata
from openhab_client import OpenHABClient


class FakeResponse:
    def __init__(self, json_data=None, status_code=200, content=b"{}"):
        self._json_data = json_data
        self.status_code = status_code
        self.content = content

    def json(self):
        return self._json_data

    def raise_for_status(self):
        return None


class RecordingSession:
    def __init__(self):
        self.headers = {}
        self.requests = []
        self.next_get = FakeResponse(
            {
                "type": "String",
                "name": "TestItem",
            }
        )
        self.next_put = FakeResponse()

    def get(self, url, **kwargs):
        self.requests.append(("GET", url, kwargs))
        return self.next_get

    def put(self, url, **kwargs):
        self.requests.append(("PUT", url, kwargs))
        return self.next_put


def _client_with_session(session):
    client = OpenHABClient("http://openhab.example")
    client.session = session
    return client


def test_create_item_excludes_metadata_from_payload():
    session = RecordingSession()
    client = _client_with_session(session)
    item = Item(
        name="TestItem",
        metadata={"semantics": ItemMetadata(value="Point", config={"relatesTo": "x"})},
    )

    client.create_item(item)

    put_request = session.requests[0]
    assert put_request[0] == "PUT"
    assert put_request[2]["json"] == {
        "type": "String",
        "name": "TestItem",
        "state": None,
        "label": None,
        "tags": [],
        "groupNames": [],
    }


def test_get_item_metadata_fetches_all_namespaces_from_item_endpoint():
    session = RecordingSession()
    session.next_get = FakeResponse(
        {
            "type": "String",
            "name": "TestItem",
            "metadata": {
                "semantics": {"value": "Point", "config": {"isPointOf": "Kitchen"}},
                "homekit": {"value": "Lighting", "config": {}},
            },
        }
    )
    client = _client_with_session(session)

    metadata = client.get_item_metadata("TestItem")

    assert session.requests == [
        (
            "GET",
            "http://openhab.example/rest/items/TestItem",
            {"params": {"metadata": ".*"}},
        )
    ]
    assert metadata["semantics"] == ItemMetadata(
        value="Point", config={"isPointOf": "Kitchen"}
    )
    assert metadata["homekit"] == ItemMetadata(value="Lighting", config={})


def test_get_item_metadata_fetches_specific_namespace_from_item_endpoint():
    session = RecordingSession()
    session.next_get = FakeResponse(
        {
            "type": "String",
            "name": "TestItem",
            "metadata": {"semantics": {"value": "Point", "config": {"relatesTo": "x"}}},
        }
    )
    client = _client_with_session(session)

    metadata = client.get_item_metadata("TestItem", namespace="semantics")

    assert session.requests == [
        (
            "GET",
            "http://openhab.example/rest/items/TestItem",
            {"params": {"metadata": "semantics"}},
        )
    ]
    assert metadata == {
        "semantics": ItemMetadata(value="Point", config={"relatesTo": "x"})
    }


def test_list_metadata_namespaces_uses_namespaces_endpoint():
    session = RecordingSession()
    session.next_get = FakeResponse(["homekit", "semantics"])
    client = _client_with_session(session)

    namespaces = client.list_metadata_namespaces("TestItem")

    assert session.requests == [
        (
            "GET",
            "http://openhab.example/rest/items/TestItem/metadata/namespaces",
            {},
        )
    ]
    assert namespaces == ["homekit", "semantics"]
