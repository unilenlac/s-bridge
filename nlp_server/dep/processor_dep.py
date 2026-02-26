
from typing import Annotated

from fastapi import Depends, Request

from nlp_server.interface.interfaces import Converter
from nlp_server.cls.Processors import *
from nlp_server.cls.Converters import *
from nlp_server.settings.settings import Settings

settings = Settings()

def converter_dep(request: Request, mode: str = "simple") -> Converter:

    match mode:
        case "simple":
                proc = request.app.state.proc
                converter: Converter = SimpleConverter(proc=proc)
                return converter
        case "full":
                proc = request.app.state.proc
                converter: Converter = FullConverter(proc=proc)
                return converter


converter = Annotated[Converter, Depends(converter_dep)]