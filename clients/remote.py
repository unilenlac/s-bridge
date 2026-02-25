import requests
from typing import Dict, Any, List
from .analysis import AnalysisClient

class RemoteAnalysisClient(AnalysisClient):
    """Client that communicates with a remote NLP microservice via HTTP."""
    
    def analyze_text(self, text: str) -> List[Dict[str, Any]]:
        """Send text to the remote server and return token data."""
        if not text.strip():
            return []
            
        try:
            response = requests.post(
                f"{self.base_url}/analyze",
                json={"text": text},
                timeout=60 # NLP parsing can take a bit of time
            )
            response.raise_for_status() # Raise exception for 4xx/5xx
            
            data = response.json()
            return data.get("tokens", [])
            
        except requests.exceptions.HTTPError as e:
            raise e
        except requests.exceptions.RequestException as e:
            # Handle specific connection errors here
            raise ConnectionError(f"Failed to connect to NLP server at {self.base_url}. Error: {e}")
