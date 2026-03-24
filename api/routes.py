from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.interfaces import Converter
from api.dependencies import converter_dep, get_processing_options, ProcessingOptions
from models.tokenization import Token, CollatexResponse
from clients.dts_client import DTSClient
from services.witness_service import WitnessService
from core.config import Settings

#APIRouteur acts as a mini FastAPI application to structure the routes.
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


class CollatexPreparationRequest(BaseModel):
    resources: List[str]
    ref: Optional[str] = None

@router.post("/dts/prepare-collatex",
    response_model=CollatexResponse,
    response_model_exclude_none=True, 
    response_model_exclude_defaults=True, 
    response_model_by_alias=True,
    description="Fetch multiple DTS resources and prepare them for Collatex")
async def prepare_collatex(
    req: CollatexPreparationRequest,
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
