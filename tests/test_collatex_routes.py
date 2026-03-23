import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from main import app
from api.dependencies import converter_dep

client = TestClient(app)

def get_mock_converter():
    class MockConverter:
        def run(self, data, normalization="lemma+pos", filter_del=True):
            return []
    return MockConverter()

app.dependency_overrides[converter_dep] = get_mock_converter

class MockCollatexService:
    def __init__(self, *args, **kwargs):
        pass
        
    async def prepare_collatex(self, resources, converter, ref=None):
        return {
            "witnesses": [
                {
                    "id": res,
                    "tokens": [
                        {"t": f"token_for_{res}", "n": f"norm_{res}"}
                    ]
                } for res in resources
            ]
        }

def test_prepare_collatex(monkeypatch):
    # Patch the CollatexService instance in the api.routes module
    from api import routes
    monkeypatch.setattr(routes, "collatex_service", MockCollatexService())
    
    response = client.post("/dts/prepare-collatex", json={"resources": ["A", "B"]})
    assert response.status_code == 200
    data = response.json()
    assert "witnesses" in data
    assert len(data["witnesses"]) == 2
    
    assert data["witnesses"][0]["id"] == "A"
    assert data["witnesses"][0]["tokens"][0]["t"] == "token_for_A"
    
    assert data["witnesses"][1]["id"] == "B"
    assert data["witnesses"][1]["tokens"][0]["t"] == "token_for_B"
