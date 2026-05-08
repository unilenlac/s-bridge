import pytest
import os

from fastapi.testclient import TestClient
from main import app
from api.dependencies import converter_dep
from models.tokenization import CollatexResponse, CollatexWitness, Token

client = TestClient(app)

def get_mock_converter():
    class MockConverter:
        def run(self, data, normalization="lemma+pos", filter_del=True):
            return []
    return MockConverter()

app.dependency_overrides[converter_dep] = get_mock_converter

from unittest.mock import AsyncMock

class MockWitnessService:
    def __init__(self, *args, **kwargs):
        self.fetcher = AsyncMock()
        self.fetcher.get_collection_name.return_value = "MockCollection"
        self.fetcher.get_collection_details.return_value = ("MockCollection", ["A", "B"])

    async def process_witnesses(self, resources, converter, options, ref=None):
        return CollatexResponse(
            witnesses=[
                CollatexWitness(
                    id=res,
                    tokens=[
                        Token(text=f"token_for_{res}", normalization=f"norm_{res}", lemma=f"lemma_{res}")
                    ]
                ) for res in resources
            ]
        )

    async def process_witnesses_by_section(
        self, resources, converter, options
    ):
        collection_name = "Auto Collection"
        return [
            os.path.join("collections", collection_name, "milestone_107.json"),
            os.path.join("collections", collection_name, "milestone_108.json"),
        ]

    async def analyse_section(self, collection_id, ref, converter, options, force=False):
        return f"/tmp/mock_prepared_{ref}.json"

    def load_prepared_section(self, filepath):
        return CollatexResponse(
            witnesses=[
                CollatexWitness(
                    id="MockRes",
                    tokens=[Token(text="mock", normalization="mock", lemma="mock")]
                )
            ]
        )



# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Tests for /dts/collate
# ---------------------------------------------------------------------------
from unittest.mock import AsyncMock, MagicMock
from models.schema import Job, JobStatus
import uuid

async def override_get_session():
    mock_session = MagicMock()
    # session.add is synchronous, but commit and refresh are async!
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    yield mock_session

def test_collate_returns_job_id(monkeypatch):
    from api import routes
    from core.database import get_session
    monkeypatch.setattr(routes, "WitnessService", MagicMock(return_value=MockWitnessService()))
    
    app.dependency_overrides[get_session] = override_get_session
    from api.dependencies import http_client
    app.dependency_overrides[http_client] = lambda: AsyncMock()

    with TestClient(app) as client:
        response = client.post(
            "/dts/process-and-collate",
            json={"collection_url": "http://testdts.com/api/dts/v1/collection?id=test_col", "ref": "mock_ref"}
        )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == JobStatus.PENDING.value

