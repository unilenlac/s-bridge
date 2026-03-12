from cltk import NLP
from fastapi import FastAPI, Depends, Query
import xml.etree.ElementTree as ET
import logging
import stanza
import uvicorn
from contextlib import asynccontextmanager 

from nlp_server.core.interfaces import Converter
from nlp_server.api.dependencies import converter_dep, get_processing_options, ProcessingOptions
from nlp_server.services.processors import ClassicalProcessor, ModernProcessor
from nlp_server.core.config import Settings
from nlp_server.models.collatex import Token


settings = Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing NLP engine...")
    
    if settings.pipeline == "modern":
        proc = ModernProcessor(stanza.Pipeline(settings.language, processors="tokenize,pos,lemma"))
    else:
        proc = ClassicalProcessor(NLP(settings.language, backend="stanza", suppress_banner=True))
    app.state.proc = proc
    logger.info("CLTK NLP engine initialized successfully.")
    
    yield

app = FastAPI(title="σ-Bridge NLP Server", description="Remote NLP parsing service using CLTK", lifespan=lifespan)
logger = logging.getLogger("nlp_server")

@app.get("/convert", response_model=list[Token] | str, response_model_exclude_none=True, response_model_exclude_defaults=True, description="Convert input text using the specified converter")
async def convert(*, text: str, options: ProcessingOptions = Depends(get_processing_options), converter: Converter = Depends(converter_dep)):
    return converter.run(text, normalization=options.normalization, filter_del=options.filter_del)  


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)