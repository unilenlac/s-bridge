from cltk import NLP
from fastapi import FastAPI
import xml.etree.ElementTree as ET
import logging
import stanza
import uvicorn
from contextlib import asynccontextmanager 
import subprocess

from services.processors import ClassicalProcessor, ModernProcessor
from core.config import Settings
from api.routes import router


settings = Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Running database migrations...")
    try:
        subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=True, capture_output=True, text=True)
        logger.info("Database check/migration completed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Database migration failed: {e.stderr}")
    except Exception as e:
        logger.error(f"Database migration generated an unexpected error: {e}")

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

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)