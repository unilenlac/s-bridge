import pytest
import os
import shutil
import json
from unittest.mock import AsyncMock, MagicMock

from services.witness_service import WitnessService
from api.dependencies import ProcessingOptions
from models.tokenization import CollatexResponse, CollatexWitness, Token
from core.config import Settings

@pytest.fixture
def mock_fetcher():
    fetcher = AsyncMock()
    fetcher.get_document.return_value = "<root>Test</root>"
    fetcher.get_collection_name.return_value = "TestCollection"
    return fetcher

@pytest.fixture
def mock_converter():
    converter = MagicMock()
    converter.run.return_value = [Token(text="test", normalization="test", lemma="test")]
    return converter

@pytest.fixture
def witness_service(mock_fetcher):
    return WitnessService(fetcher=mock_fetcher)

@pytest.fixture
def options():
    return ProcessingOptions(normalization="lemma+pos", filter_del=True)

def test_get_section_filepath(witness_service):
    settings = Settings()
    path = witness_service.get_section_filepath("Coll1", "ref1")
    assert "Coll1" in path
    assert "milestone_ref1.json" in path
    assert path.startswith(settings.output_dir)

@pytest.mark.anyio
async def test_prepare_section_if_needed(witness_service, mock_converter, options):

    settings = Settings()
    # Ensure output_dir is cleared for test
    if os.path.exists(settings.output_dir):
        shutil.rmtree(settings.output_dir)
    
    ref = "101"
    filepath = await witness_service.prepare_section_if_needed(
        resources=["res1"],
        ref=ref,
        converter=mock_converter,
        options=options
    )
    
    assert os.path.exists(filepath)
    with open(filepath, "r") as f:
        data = json.load(f)
        assert "witnesses" in data
        assert data["witnesses"][0]["id"] == "res1"

@pytest.mark.anyio
async def test_load_prepared_section(witness_service, mock_converter, options):

    ref = "102"
    filepath = await witness_service.prepare_section_if_needed(
        resources=["res1"],
        ref=ref,
        converter=mock_converter,
        options=options
    )
    
    response = witness_service.load_prepared_section(filepath)
    assert isinstance(response, CollatexResponse)
    assert len(response.witnesses) == 1
    assert response.witnesses[0].tokens[0].text == "test"

def test_save_collation_result(witness_service):
    settings = Settings()
    # Ensure collation_dir is cleared for test
    if os.path.exists(settings.collation_dir):
        shutil.rmtree(settings.collation_dir)
        
    collection = "TestColl"
    ref = "103"
    result = "DOT DATA"
    format = "text/plain"
    
    path = witness_service.save_collation_result(collection, ref, result, format)
    
    assert os.path.exists(path)
    assert "TestColl" in path
    assert "milestone_103.dot" in path
    with open(path, "r") as f:
        assert f.read() == "DOT DATA"

    # Test JSON saving
    json_result = {"key": "value"}
    path_json = witness_service.save_collation_result(collection, "104", json_result, "application/json")
    assert path_json.endswith(".json")
    with open(path_json, "r") as f:
        data = json.load(f)
        assert data == json_result
