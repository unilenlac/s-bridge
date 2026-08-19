import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from clients.collatex_client import CollatexClient
from models.schema import Job


@pytest.mark.anyio
async def test_collatex_dekker_success():
    mock_http = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"table": [["a", "a"]]}
    mock_resp.raise_for_status.return_value = None
    mock_http.post.return_value = mock_resp

    client = CollatexClient(base_url="http://localhost:7369", http_client=mock_http)
    payload = {"witnesses": [{"id": "w1", "tokens": [{"t": "a", "n": "a"}]}]}

    result, algo, fell_back = await client.collate_with_fallback(
        payload=payload, algorithm="dekker", dekker_timeout=5.0, ref_id="101"
    )

    assert algo == "dekker"
    assert fell_back is False
    assert result == {"table": [["a", "a"]]}
    assert mock_http.post.call_count == 1


@pytest.mark.anyio
async def test_collatex_dekker_timeout_fallback_to_needleman():
    mock_http = AsyncMock()

    # First call (dekker) raises TimeoutException, second call (needleman-wunsch) succeeds
    mock_success_resp = MagicMock()
    mock_success_resp.json.return_value = {"table": [["a", "a"]]}
    mock_success_resp.raise_for_status.return_value = None

    mock_http.post.side_effect = [
        httpx.TimeoutException("Read timed out"),
        mock_success_resp,
    ]

    client = CollatexClient(base_url="http://localhost:7369", http_client=mock_http)
    payload = {"witnesses": [{"id": "w1", "tokens": [{"t": "a", "n": "a"}]}]}

    result, algo, fell_back = await client.collate_with_fallback(
        payload=payload, algorithm="dekker", dekker_timeout=5.0, ref_id="142"
    )

    assert algo == "needleman-wunsch"
    assert fell_back is True
    assert result == {"table": [["a", "a"]]}
    assert mock_http.post.call_count == 2


@pytest.mark.anyio
async def test_collatex_explicit_algorithm_no_fallback():
    mock_http = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"table": [["a", "a"]]}
    mock_resp.raise_for_status.return_value = None
    mock_http.post.return_value = mock_resp

    client = CollatexClient(base_url="http://localhost:7369", http_client=mock_http)
    payload = {"witnesses": [{"id": "w1", "tokens": [{"t": "a", "n": "a"}]}]}

    result, algo, fell_back = await client.collate_with_fallback(
        payload=payload, algorithm="medite", ref_id="101"
    )

    assert algo == "medite"
    assert fell_back is False
    assert mock_http.post.call_count == 1


@pytest.mark.anyio
async def test_collatex_joined_and_transpositions():
    mock_http = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"table": [["a", "a"]]}
    mock_resp.raise_for_status.return_value = None
    mock_http.post.return_value = mock_resp

    client = CollatexClient(base_url="http://localhost:7369", http_client=mock_http)
    payload = {"witnesses": [{"id": "w1", "tokens": [{"t": "a", "n": "a"}]}]}

    result, algo, fell_back = await client.collate_with_fallback(
        payload=payload,
        algorithm="dekker",
        joined=False,
        transpositions=False,
        ref_id="101",
    )

    assert algo == "dekker"
    assert fell_back is False
    # Verify post was called with joined=False and transpositions=False in json payload
    called_json = mock_http.post.call_args[1]["json"]
    assert called_json["joined"] is False
    assert called_json["transpositions"] is False
    assert called_json["algorithm"] == "dekker"


@pytest.mark.anyio
async def test_collatex_token_comparator():
    mock_http = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"table": [["a", "a"]]}
    mock_resp.raise_for_status.return_value = None
    mock_http.post.return_value = mock_resp

    client = CollatexClient(base_url="http://localhost:7369", http_client=mock_http)
    payload = {"witnesses": [{"id": "w1", "tokens": [{"t": "a", "n": "a"}]}]}

    # 1. Test with default equality
    result, algo, fell_back = await client.collate_with_fallback(
        payload=payload,
        token_comparator={"type": "equality"},
        ref_id="101",
    )
    assert algo == "dekker"
    called_json = mock_http.post.call_args[1]["json"]
    assert called_json["tokenComparator"] == {"type": "equality"}

    # 2. Test with levenshtein distance
    result, algo, fell_back = await client.collate_with_fallback(
        payload=payload,
        token_comparator={"type": "levenshtein", "distance": 2},
        ref_id="102",
    )
    called_json = mock_http.post.call_args[1]["json"]
    assert called_json["tokenComparator"] == {"type": "levenshtein", "distance": 2}


def test_job_model_fallback_refs():
    job = Job(
        collection_url="http://test.com/dts",
        fallback_refs=["142"],
    )
    assert job.fallback_refs == ["142"]
    assert job.algorithm == "dekker"
    assert job.joined is True
    assert job.transpositions is True
    assert job.token_comparator == {"type": "equality"}
