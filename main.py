from cltk import NLP
from fastapi import FastAPI, Request
import logging
import stanza
import uvicorn
import httpx
from contextlib import asynccontextmanager
from fastapi.openapi.utils import get_openapi

from core.logging import setup_logging

from services.processors import ClassicalProcessor, ModernProcessor
from core.config import Settings
from api.routes import router


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = setup_logging(settings)

    logger.info("Initializing NLP engine...")

    if settings.pipeline == "modern":
        proc = ModernProcessor(
            stanza.Pipeline(settings.language, processors="tokenize,pos,lemma")
        )
    else:
        proc = ClassicalProcessor(
            NLP(settings.language, backend="stanza", suppress_banner=True)
        )
    app.state.proc = proc
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.collatex_timeout, connect=10.0)
    )
    logger.info("CLTK NLP engine initialized successfully.")

    yield

    await app.state.http_client.aclose()


app = FastAPI(
    title="σ-Bridge NLP Server",
    description="Remote NLP parsing service using CLTK/Stanza",
    lifespan=lifespan,
)

@app.get("/app")
def read_main(request: Request):
    return {"message": "Hello World", "root_path": request.scope.get("root_path")}

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=settings.oa_app_name,
        description=settings.oa_app_description,
        version="0.1",
        servers=settings.oa_app_url,
        contact={"name": settings.oa_app_author, "email": settings.oa_app_author_email},
        routes=app.routes
    )
    [openapi_schema["components"]["schemas"].pop(model, None) for model in ["UrlComponent", "CollectionParams", "DocumentParams", "NavigationParams", "IndexMetadataModel"]]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

logger = logging.getLogger("nlp_server")

app.include_router(router)
app.openapi = custom_openapi

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", root_path=f"{settings.app_root_path}", port=int(f"{settings.app_port}"), log_level="info", access_log=True)
