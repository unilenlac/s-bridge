import pytest
import os
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
    service = WitnessService()
    return service


@pytest.mark.anyio
async def test_analyse_section():
    mock_fetcher = AsyncMock()
    mock_fetcher.get_collection_name.return_value = "test_collection"
    mock_fetcher.get_collection_details.return_value = (
        "test_collection",
        ["res1", "res2"],
    )

    mock_converter = MagicMock()
    options = ProcessingOptions(normalization="none", filter_del=False)

    service = WitnessService()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Patch the settings output dir explicitly to use temp directory
        with patch("services.witness_service.Settings") as mock_settings:
            mock_settings.return_value.nlp_analysis_dir = temp_dir

            # Setup dummy responses for process_witnesses
            # Side effect allowing us to mock responses dynamically based on input resources
            async def process_witnesses_side_effect(*args, **kwargs):
                witnesses = []
                resources = ["res1", "res2"]
                for res in resources:
                    witnesses.append(
                        CollatexWitness(
                            id=res,
                            tokens=[{"t": "test", "id": "t1", "n": "1", "lem": "test"}],
                        )
                    )
                return CollatexResponse(witnesses=witnesses)

            # Using patch.object to mock process_witnesses logic
            with patch.object(
                service, "process_witnesses", side_effect=process_witnesses_side_effect
            ) as mock_process:
                mock_fetcher.get_collection_details.return_value = (
                    "test_collection",
                    ["res1", "res2"],
                )
                filepath = await service.analyse_section(
                    converter=mock_converter,
                    options=options,
                    http_client=AsyncMock(),
                    path=os.path.join(temp_dir, "mock_path.json"),
                )

                assert os.path.exists(filepath)
                mock_process.assert_called_once()
                mock_process.reset_mock()

                # Verify initial file content
                data = service.load_prepared_section(filepath)
                assert len(data.witnesses) == 2
                assert {w.id for w in data.witnesses} == {"res1", "res2"}


@pytest.mark.anyio
async def test_dts_preparator_collection_member_error():
    from services.preparators import DtsPreparator
    from core.exceptions import DtsError
    from core.config import Settings

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "@id": "s-bridge",
        "@type": "Collection",
        "member": [
            {
                "@id": "sb-ab",
                "@type": "Collection",
                "collection": "/api/dts/v1/collection?id=sb-ab{?id,page,nav}",
            }
        ],
    }
    mock_client.get.return_value = mock_response

    with pytest.raises(DtsError, match="DTS Error: resources are collection type"):
        await DtsPreparator.run(
            url="http://ftsr-dev.unil.ch:8000/api/dts/v1/collection?id=s-bridge",
            target_ref=None,
            job_id="test_job",
            http_client=mock_client,
            settings=Settings(),
        )
