from cltk import NLP
from fastapi import FastAPI, Depends, Query
import xml.etree.ElementTree as ET
import logging
import stanza
import uvicorn
from contextlib import asynccontextmanager 

from nlp_server.interface.interfaces import Converter
from nlp_server.dep.processor_dep import converter_dep
from nlp_server.cls.Processors import ClassicalProcessor, ModernProcessor
from nlp_server.settings.settings import Settings
from nlp_server.model.collatex import Token


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

dummy_data = """<div>""" \
            """<pb n="f.193v"/>""" \
            """<lb n="1"/><hi>κ</hi>ατὰ τὸν καιρὸν ἐκεῖνον τραϊανοῦ τοῦ βασιλέως παρειληφότος τῆν τῶν ρω-""" \
            """<lb n="2" break="no"/>μαίων ἀρχὴν· μετὰ τὸ μαρτυρῆσαι ἐν ὀγδόω ἔτει τῆς βασιλείας αὐτοῦ σίμω-""" \
            """<lb n="3" break="no"/>να τὸν τοῦ κλωπᾶ <seg>ἐπίσκοπον</seg> ὄντα ϊεροσολύμων· δεύτερον γενόμενον""" \
            """<lb n="4"/>ἐπίσης τοῦ μετὰ ἰάκωβον τὸν χρηματίσαντα ἀδελφὸν τοῦ κυρίου· τῆς""" \
            """<lb n="5"/>ἐκεῖσε ἐκκλησίας· φίλιππος ὁ ἀπόστολος διἐρχόμενος τὰ τῆς λυδίας καὶ ἀσίας""" \
            """<lb n="6"/>πόλεις καὶ χώρας κατήγγειλεν πάσιν τὸ εὐαγγέλιον τοῦ χριστοῦ· """ \
            """</div>"""

@app.get("/convert", response_model=list[Token] | str, response_model_exclude_none=True, response_model_exclude_defaults=True, description="Convert input text using the specified converter")
async def convert(*, text: str, normalization: str = Query("lemma+pos", description="Token normalization string. Options: lemma+pos, lemma, text, original"), filter_del: bool = Query(True, description="Filter out tokens that are marked as deleted"), converter: Converter = Depends(converter_dep)):
    return converter.run(text, normalization=normalization, filter_del=filter_del)  


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)