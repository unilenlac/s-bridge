# processor protocol
from typing import Protocol, Any, Dict, List, Tuple, Optional
import xml.etree.ElementTree as ET

from httpx import AsyncClient

class Processor(Protocol):
    def __init__(self, pipeline: Any):
        ...
    def process(self, data: Any, normalization: str = "lemma+pos") -> Any:
        ...

class Converter(Protocol):
    def run(self, data: str, normalization: str = "lemma+pos", filter_del: bool = True) -> Any:
        ...

class Parser(Protocol):
    def __init__(self, abbr_file: Optional[str]):
        ...
    def parse(self, data: str) -> Tuple[str, List[Tuple[int, int, Dict[str, Any]]]]:
        ...

class CollationPreparator(Protocol):
    @staticmethod
    async def run(url: str, http_client: AsyncClient) -> str:
        ...