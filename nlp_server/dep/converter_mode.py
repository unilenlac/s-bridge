from typing import Annotated, Literal
from fastapi import Depends, Request, Query

from nlp_server.interface.interfaces import Converter
from nlp_server.cls.TEIParser import TEIParser
from nlp_server.cls.Converters import EnrichedStrategyConverter, RawStrategyConverter
from nlp_server.settings.settings import Settings

settings = Settings()


FormatType = Literal["tei", "json", "text"]
StrategyType = Literal["enriched", "raw"]

def converter_dep(
    request: Request, 
    format: FormatType = Query("tei", description="Input data format"), 
    strategy: StrategyType = Query("enriched", description="Parsing complexity strategy")
) -> Converter:
    proc = request.app.state.proc

    if strategy == "raw":
        return RawStrategyConverter(proc=proc)

    elif strategy == "enriched":
        match format:
            case "tei":
                parser = TEIParser(abbr_file="utils/abbr_classical_greek.csv")
            case "json":
                #Not implemented
                raise NotImplementedError("JSON Support is coming soon! TM")
            case "text":
                #Not implemented
                raise NotImplementedError("Plain text support is coming soon! TM")
            case _:
                #Technically unreachable due to FastAPI validation but good practice
                raise ValueError(f"Unsupported format: {format}")
        return EnrichedStrategyConverter(proc=proc, parser=parser)