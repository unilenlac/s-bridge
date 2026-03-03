# processor protocol
from typing import Protocol, Any
from xml.etree.ElementTree import Element

class Processor(Protocol):
    def __init__(self, pipeline: Any):
        ...
    def process(self, data: Any) -> Any:
        ...

class Converter(Protocol):
    def run(self, data: Element) -> Any:
        ...

class Parser(Protocol):
    def __init__(self, abbr_file: Optional[str]):
        ...
    def parse(self, data: Any) -> Tuple[str, List[Tuple[int, int, Dict[str, Any]]]]:
        ...