import pytest
import json
import asyncio
import httpx
from clients.dts_client import DTSClient


# ---------------------------------------------------------------------------
# Tests for get_document
# ---------------------------------------------------------------------------

def test_get_document(monkeypatch):
    class MockResponse:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            pass

    class MockAsyncClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def get(self, url, params=None):
            assert url.startswith("http://test/api/dts/v1/document")
            assert params["resource"] == "res1"
            assert params["media_type"] == "text/xml"
            if "ref" in params:
                assert params["ref"] == "ref1"
            return MockResponse("<root>Test XML</root>")

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    client = DTSClient(base_url="http://test")
    xml = asyncio.run(client.get_document("res1", ref="ref1"))
    assert xml == "<root>Test XML</root>"


# ---------------------------------------------------------------------------
# Tests for get_navigation
# ---------------------------------------------------------------------------

def test_get_navigation_single_page(monkeypatch):
    """All refs fit on one page — no pagination loop."""

    nav_response = {
        "member": [
            {"identifier": "107", "citeType": "milestone"},
            {"identifier": "108", "citeType": "milestone"},
        ],
        "view": {
            "next": "http://test/nav?page=1",
            "last": "http://test/nav?page=1",  # next == last → stop
        }
    }

    class MockJsonResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return nav_response

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def get(self, url, params=None):
            assert "navigation" in url
            assert params["resource"] == "res1"
            assert params["down"] == 1
            return MockJsonResponse()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    client = DTSClient(base_url="http://test")
    members = asyncio.run(client.get_members("res1"))

    assert len(members) == 2
    assert members[0] == {"identifier": "107", "citeType": "milestone"}
    assert members[1] == {"identifier": "108", "citeType": "milestone"}


def test_get_navigation_multiple_pages(monkeypatch):
    """Pagination: two pages, each with one member."""

    page1 = {
        "member": [{"identifier": "107", "citeType": "milestone"}],
        "view": {
            "next": "http://test/nav?page=2",
            "last": "http://test/nav?page=2",  # next == last on page 2
        }
    }
    page2 = {
        "member": [{"identifier": "108", "citeType": "milestone"}],
        "view": {
            "next": "http://test/nav?page=2",
            "last": "http://test/nav?page=2",
        }
    }

    call_count = {"n": 0}

    class MockJsonResponse:
        def __init__(self, data):
            self._data = data
        def raise_for_status(self):
            pass
        def json(self):
            return self._data

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def get(self, url, params=None):
            call_count["n"] += 1
            # First call returns page1 (next != last), second call returns page2
            if call_count["n"] == 1:
                # Simulate next != last so the loop continues
                p1 = {**page1, "view": {"next": "http://test/nav?page=2", "last": "http://test/nav?page=2"}}
                # Override: make next != last for page 1
                p1["view"]["next"] = "http://test/nav?page=2"
                p1["view"]["last"] = "http://test/nav?page=2_END"
                return MockJsonResponse(p1)
            else:
                return MockJsonResponse(page2)

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    client = DTSClient(base_url="http://test")
    members = asyncio.run(client.get_members("res1"))

    assert len(members) == 2
    assert len(members) == 2
    assert call_count["n"] == 2


def test_get_cite_type(monkeypatch):
    nav_response = {
        "citeType": "milestone",
        "member": []
    }

    class MockJsonResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return nav_response

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def get(self, url, params=None):
            assert "navigation" in url
            assert params["resource"] == "res1"
            assert params["ref"] == "ref1"
            return MockJsonResponse()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    client = DTSClient(base_url="http://test")
    cite_type = asyncio.run(client.get_cite_type("res1", "ref1"))

    assert cite_type == "milestone"
