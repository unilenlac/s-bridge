import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from core.interfaces import Converter
from api.dependencies import converter_dep, get_processing_options, ProcessingOptions
from models.tokenization import Token, CollatexResponse
from clients.dts_client import DTSClient
from clients.collatex_client import CollatexClient
from services.witness_service import WitnessService
from core.config import Settings

# APIRouter acts as a mini FastAPI application to structure the routes.
router = APIRouter()

settings = Settings()
dts_client = DTSClient(base_url=settings.dts_api_base_url)
collatex_client = CollatexClient(base_url=settings.collatex_api_base_url)
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
        "Optionally scope to a specific passage ref. "
        "[DEPRECATED] Use /dts/prepare-collatex/split instead."
    ),
    deprecated=True)

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

# ---------------------------------------------------------------------------
# Collate endpoint — fetch witnesses and proxy them to the CollateX Service
# ---------------------------------------------------------------------------

@router.post("/dts/collate",
    description=(
        "Fetch multiple DTS resources, prepare them, and send them to the "
        "CollateX service for alignment. Returns the response from CollateX."
    ))
async def collate_resources(
    req: CollatexWitnessRequest,
    output_format: str = Query("application/json", description="Output format"),
    options: ProcessingOptions = Depends(get_processing_options),
    converter: Converter = Depends(converter_dep)
):
    try:
        # 1. Identify all refs (sections) to process
        if req.ref:
            refs = [req.ref]
        else:
            nav = await dts_client.get_navigation(req.resources[0])
            refs = [m["identifier"] for m in nav]

        # 2. Iterate and collate each section (always through prepared files)
        # 2. Process sections and save results to disk
        collection_name = await witness_service.fetcher.get_collection_name(req.resources[0])
        saved_files = {}
        
        for r in refs:
            # Prepare section if needed
            path = await witness_service.prepare_section_if_needed(req.resources, r, converter, options)
            ready_data = witness_service.load_prepared_section(path)
            
            # Collate
            result = await collatex_client.collate(
                payload=ready_data.model_dump(by_alias=True, exclude_none=True),
                output_format=output_format
            )
            
            # Persist result to disk
            # For simplicity we assume milestone here, but we could improve this by passing citeType
            saved_path = witness_service.save_collation_result(
                collection_name=collection_name,
                ref_id=r,
                result=result,
                output_format=output_format
            )
            saved_files[r] = saved_path

        # 3. Return the mapping of refs to file paths
        return {
            "collection": collection_name,
            "format": output_format,
            "total_sections": len(saved_files),
            "results": saved_files
        }
        
    except Exception as e:
        logger.error(f"Error in collate_resources: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



