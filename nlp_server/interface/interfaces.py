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