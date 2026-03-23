import pytest
import httpx
import asyncio
from clients.dts_client import DTSClient

def test_get_document(monkeypatch):
    class MockResponse:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            pass

    class MockAsyncClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def get(self, url, params=None):
            assert url.startswith("http://test/api/dts/v1/document/")
            assert params["resource"] == "res1"
            assert params["media_type"] == "text/xml"
            if "ref" in params:
                assert params["ref"] == "ref1"
            return MockResponse("<root>Test XML</root>")

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
    
    client = DTSClient(base_url="http://test")
    xml = asyncio.run(client.get_document("res1", ref="ref1"))
    assert xml == "<root>Test XML</root>"
