from abc import ABC, abstractmethod
from typing import Dict, Any, List

class AnalysisClient(ABC):
    """Abstract base class for NLP analysis clients."""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        
    @abstractmethod
    def analyze_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Send raw text string to the server and return parsed token data.
        Returns a list of token dictionaries.
        """
        pass
