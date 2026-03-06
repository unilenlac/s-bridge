# processor protocol
from typing import Protocol, Any, Dict, List, Tuple, Optional
import xml.etree.ElementTree as ET

class Processor(Protocol):
    def __init__(self, pipeline: Any):
        ...
    def process(self, data: Any) -> Any:
        ...

class Converter(Protocol):
    def run(self, data: ET.Element) -> Any:
        ...

class Parser(Protocol):
    def __init__(self, abbr_file: Optional[str]):
        ...
    def parse(self, data: ET.Element) -> Tuple[str, List[Tuple[int, int, Dict[str, Any]]]]:
        ...