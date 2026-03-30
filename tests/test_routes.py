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

class MockWitnessService:
    def __init__(self, *args, **kwargs):
        pass

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


# ---------------------------------------------------------------------------
# Tests for /dts/prepare-collatex/witness  (renamed from /dts/prepare-collatex)
# ---------------------------------------------------------------------------

def test_prepare_collatex_witness(monkeypatch):
    from api import routes
    monkeypatch.setattr(routes, "witness_service", MockWitnessService())

    response = client.post("/dts/prepare-collatex/whole", json={"resources": ["A", "B"]})
    assert response.status_code == 200
    data = response.json()
    assert "witnesses" in data
    assert len(data["witnesses"]) == 2

    assert data["witnesses"][0]["id"] == "A"
    assert data["witnesses"][0]["tokens"][0]["t"] == "token_for_A"

    assert data["witnesses"][1]["id"] == "B"
    assert data["witnesses"][1]["tokens"][0]["t"] == "token_for_B"


def test_prepare_collatex_witness_with_ref(monkeypatch):
    from api import routes
    monkeypatch.setattr(routes, "witness_service", MockWitnessService())

    response = client.post(
        "/dts/prepare-collatex/whole",
        json={"resources": ["A"], "ref": "109"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["witnesses"]) == 1


# ---------------------------------------------------------------------------
# Tests for /dts/prepare-collatex/by-section
# ---------------------------------------------------------------------------

def test_prepare_collatex_split(monkeypatch):
    from api import routes
    monkeypatch.setattr(routes, "witness_service", MockWitnessService())

    response = client.post(
        "/dts/prepare-collatex/split",
        json={"resources": ["A", "B"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert "written_files" in data
    assert data["total_sections"] == 2
    assert any("milestone_107.json" in f for f in data["written_files"])
    assert any("milestone_108.json" in f for f in data["written_files"])


def test_prepare_collatex_split_works(monkeypatch):
    """Should succeed and auto-fetch."""
    from api import routes
    monkeypatch.setattr(routes, "witness_service", MockWitnessService())

    response = client.post(
        "/dts/prepare-collatex/split",
        json={"resources": ["A", "B"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert "written_files" in data
    assert any("Auto Collection" in f for f in data["written_files"])
