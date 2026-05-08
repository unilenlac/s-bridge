import logging

from pathlib import Path
from typing import Literal, Annotated, Optional, Tuple
from fastapi import Depends, Request, Query
from httpx import AsyncClient, Timeout
from pydantic import BaseModel

from core.interfaces import Converter
from services.tei_parser import TEIParser
from services.converters import EnrichedStrategyConverter, RawStrategyConverter
from core.config import Settings

settings = Settings()

FormatType = Literal["tei", "json", "text"]
StrategyType = Literal["enriched", "raw"]

# Resolve the tag dictionary once at import time (fail-fast on invalid config).
_tag_dict = settings.load_tag_dictionary()


class ProcessingOptions(BaseModel):
    normalization: str
    filter_del: bool

async def get_processing_options(
    normalization: str = Query("lemma+pos", description="Token normalization string. Options: lemma+pos, lemma, text"),
    filter_del: bool = Query(True, description="Filter out tokens that are marked as deleted")
) -> ProcessingOptions:
    return ProcessingOptions(normalization=normalization, filter_del=filter_del)

def converter_dep(
    request: Request, 
    format: FormatType = Query("tei", description="Input data format"), 
    strategy: StrategyType = Query("enriched", description="Parsing complexity strategy"),
) -> Converter:
    proc = request.app.state.proc

    if strategy == "raw":
        return RawStrategyConverter(proc=proc)

    elif strategy == "enriched":
        match format:
            case "tei":
                utils_dir = Path(__file__).parent.parent / "utils"
                abbr_file = utils_dir / "abbr_classical_greek.csv"
                parser = TEIParser(abbr_file=str(abbr_file), custom_tags=_tag_dict)
            case "json":
                #Not implemented
                raise NotImplementedError("JSON Support is coming soon! TM")
            case _:
                #Technically unreachable due to FastAPI validation but good practice
                raise ValueError(f"Unsupported format: {format}")
        return EnrichedStrategyConverter(proc=proc, parser=parser)

class ClientParams(BaseModel):
    # not really necessary. parameters can be passed on the fly at the request level.
    follow_redirects: bool = False
    timeout: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None

def http_client(request: Request):
    return request.app.state.http_client

http_client = Annotated[AsyncClient, Depends(http_client)]