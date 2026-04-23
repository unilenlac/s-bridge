import pytest
import os
import json
import tempfile
from unittest.mock import AsyncMock, patch, MagicMock

from services.witness_service import WitnessService
from models.tokenization import CollatexResponse, CollatexWitness
from api.dependencies import ProcessingOptions


@pytest.fixture
def mock_fetcher():
    fetcher = AsyncMock()
    # Always return a dummy collection name
    fetcher.get_collection_name.return_value = "dummy_collection"
    return fetcher


@pytest.fixture
def mock_converter():
    return MagicMock()


@pytest.fixture
def options():
    return ProcessingOptions(normalization="none", filter_del=False)


@pytest.fixture
def witness_service(mock_fetcher):
    # Setup witness service with a temporary directory
    service = WitnessService(fetcher=mock_fetcher)
    return service


@pytest.mark.anyio
async def test_prepare_section_smart_update():
    mock_fetcher = AsyncMock()
    mock_fetcher.get_collection_name.return_value = "test_collection"
    mock_fetcher.get_collection_details.return_value = ("test_collection", ["res1", "res2"])
    
    mock_converter = MagicMock()
    options = ProcessingOptions(normalization="none", filter_del=False)

    service = WitnessService(fetcher=mock_fetcher)

    with tempfile.TemporaryDirectory() as temp_dir:
        # Patch the settings output dir explicitly to use temp directory
        with patch("services.witness_service.Settings") as mock_settings:
            mock_settings.return_value.output_dir = temp_dir
            
            # Setup dummy responses for process_witnesses
            # Side effect allowing us to mock responses dynamically based on input resources
            async def process_witnesses_side_effect(resources, converter, options, ref):
                witnesses = []
                for res in resources:
                    witnesses.append(CollatexWitness(id=res, tokens=[{"t": "test", "id": "t1", "n": "1", "lem": "test"}]))
                return CollatexResponse(witnesses=witnesses)
            
            # Using patch.object to mock process_witnesses logic
            with patch.object(service, 'process_witnesses', side_effect=process_witnesses_side_effect) as mock_process:
                
                # 1. 1st Call - Fresh (no file exists)
                mock_fetcher.get_collection_details.return_value = ("test_collection", ["res1", "res2"])
                filepath = await service.prepare_section_if_needed(
                    collection_id="mock_col",
                    ref="sec1",
                    converter=mock_converter,
                    options=options
                )
                
                assert os.path.exists(filepath)
                mock_process.assert_called_once()
                mock_process.reset_mock()
                
                # Verify initial file content
                data = service.load_prepared_section(filepath)
                assert len(data.witnesses) == 2
                assert {w.id for w in data.witnesses} == {"res1", "res2"}

                # 2. 2nd Call - Add single missing resource (append mode)
                mock_fetcher.get_collection_details.return_value = ("test_collection", ["res1", "res2", "res3"])
                await service.prepare_section_if_needed(
                    collection_id="mock_col",
                    ref="sec1",
                    converter=mock_converter,
                    options=options
                )
                
                # Verify that process_witnesses was only called for missing matching ones
                mock_process.assert_called_once()
                assert mock_process.call_args.kwargs["resources"] == ["res3"]
                mock_process.reset_mock()
                
                # Verify updated file content
                data = service.load_prepared_section(filepath)
                assert len(data.witnesses) == 3
                assert {w.id for w in data.witnesses} == {"res1", "res2", "res3"}

                # 3. 3rd Call - Exact Match (no operation)
                mock_fetcher.get_collection_details.return_value = ("test_collection", ["res1", "res3"])
                await service.prepare_section_if_needed(
                    collection_id="mock_col", # subset
                    ref="sec1",
                    converter=mock_converter,
                    options=options
                )
                
                # Should not be called since both exist
                mock_process.assert_not_called()
