from xml.etree.ElementTree import Element
from cltk.core.data_types import Doc

from nlp_server.interface.interfaces import Processor
from nlp_server.model.collatex import Token

class SimpleConverter:
    def __init__(self, proc: Processor):
        self.processor = proc
    def run(self, data: Element) -> str:  # Example: convert input text to uppercase
        return "".join(data.itertext())

class FullConverter:
    def __init__(self, proc: Processor):
        self.processor = proc
    def run(self, data: Element) -> str:
        pre_proced = "".join(data.itertext())
        analysis: Doc = self.processor.process(pre_proced)
        result = []
        for word in analysis.words:
            token = Token(text=word.string, lemma=word.lemma)
            result.append(token)
        return result