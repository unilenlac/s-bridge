from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.interfaces import Converter
from api.dependencies import converter_dep, get_processing_options, ProcessingOptions
from models.tokenization import Token, CollatexResponse
from clients.dts_client import DTSClient
from services.witness_service import WitnessService
from core.config import Settings

# APIRouter acts as a mini FastAPI application to structure the routes.
router = APIRouter()

settings = Settings()
dts_client = DTSClient(base_url=settings.dts_api_base_url)
witness_service = WitnessService(fetcher=dts_client)


class ConvertRequest(BaseModel):
    text: str

@router.post("/convert", response_model=list[Token],
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
    description="[DEPRECATED] Convert input text using the specified converter",
    deprecated=True)
async def convert(req: ConvertRequest,
    options: ProcessingOptions = Depends(get_processing_options),
    converter: Converter = Depends(converter_dep)):
    return converter.run(req.text, normalization=options.normalization, filter_del=options.filter_del)


# ---------------------------------------------------------------------------
# Witness endpoint — fetch multiple witnesses for Collatex (optional ref)
# ---------------------------------------------------------------------------

class CollatexWitnessRequest(BaseModel):
    resources: List[str]
    ref: Optional[str] = None

@router.post("/dts/prepare-collatex/whole",
    response_model=CollatexResponse,
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
    response_model_by_alias=True,
    description=(
        "Fetch multiple DTS resources and prepare them for Collatex. "
        "Optionally scope to a specific passage ref."
    ))
async def prepare_collatex_whole(
    req: CollatexWitnessRequest,
    options: ProcessingOptions = Depends(get_processing_options),
    converter: Converter = Depends(converter_dep)
):
    try:
        result = await witness_service.process_witnesses(
            resources=req.resources,
            converter=converter,
            options=options,
            ref=req.ref
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# ---------------------------------------------------------------------------
# By-section endpoint — split by top-level refs, write one file per section
# ---------------------------------------------------------------------------

class CollatexBySectionRequest(BaseModel):
    resources: List[str]

class CollatexBySectionResponse(BaseModel):
    written_files: List[str]
    total_sections: int

@router.post("/dts/prepare-collatex/split",
    response_model=CollatexBySectionResponse,
    description=(
        "Fetch multiple DTS resources, split by top-level sections (e.g. milestones), "
        "and write one Collatex JSON file per section to disk. "
        "Files are written to: <output_dir>/<collection_name>/<citeType>_<identifier>.json"
    ))
async def prepare_collatex_split(
    req: CollatexBySectionRequest,
    options: ProcessingOptions = Depends(get_processing_options),
    converter: Converter = Depends(converter_dep)
):
    try:
        written = await witness_service.process_witnesses_by_section(
            resources=req.resources,
            converter=converter,
            options=options,
        )
        return CollatexBySectionResponse(
            written_files=written,
            total_sections=len(written),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
