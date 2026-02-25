import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from clients.analysis import AnalysisClient
from clients.local import LocalCltkClient
from clients.remote import RemoteAnalysisClient
import requests

def test_analysis_client_abc():
    """Verify that AnalysisClient cannot be instantiated directly."""
    with pytest.raises(TypeError):
        client = AnalysisClient(host="localhost", port=8000)

def test_remote_client_success():
    """Verify that RemoteAnalysisClient correctly parses successful JSON responses."""
    client = RemoteAnalysisClient(host="testserver", port=8000)
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "tokens": [
            {"t": "Hello", "lem": "hello", "pos": "INTJ"},
            {"t": "world", "lem": "world", "pos": "NOUN"}
        ]
    }
    
    with patch('requests.post', return_value=mock_response) as mock_post:
        tokens = client.analyze_text("Hello world")
        
        # Verify the post request was formatted correctly
        mock_post.assert_called_once_with(
            "http://testserver:8000/analyze",
            json={"text": "Hello world"},
            timeout=60
        )
        # Verify the tokens were extracted
        assert len(tokens) == 2
        assert tokens[0]["t"] == "Hello"

def test_remote_client_empty_text():
    """Verify that empty text returns an empty list without making an HTTP call."""
    client = RemoteAnalysisClient(host="testserver", port=8000)
    
    with patch('requests.post') as mock_post:
        tokens = client.analyze_text("   ")
        mock_post.assert_not_called()
        assert tokens == []

def test_remote_client_http_error():
    """Verify that HTTP errors are bubbled up properly."""
    client = RemoteAnalysisClient(host="testserver", port=8000)
    
    # Setup a mock response that raises an HTTPError when raise_for_status is called
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error")
    
    with patch('requests.post', return_value=mock_response):
        with pytest.raises(requests.exceptions.HTTPError):
            client.analyze_text("Error text")

def test_remote_client_connection_error():
    """Verify that connection errors are handled."""
    client = RemoteAnalysisClient(host="badserver", port=9999)
    
    with patch('requests.post', side_effect=requests.exceptions.ConnectionError("Failed to connect")):
        with pytest.raises(ConnectionError):
            client.analyze_text("Connection text")

