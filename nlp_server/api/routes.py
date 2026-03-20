from fastapi import APIRouter, Depends
from pydantic import BaseModel

from nlp_server.core.interfaces import Converter
from nlp_server.api.dependencies import converter_dep, get_processing_options, ProcessingOptions
from nlp_server.models.collatex import Token

#APIRouteur acts as a mini FastAPI application to structure the routes.
router = APIRouter()

class ConvertRequest(BaseModel):
    text: str

@router.post("/convert", response_model=list[Token] | str, response_model_exclude_none=True, response_model_exclude_defaults=True, description="Convert input text using the specified converter")
async def convert(req: ConvertRequest, options: ProcessingOptions = Depends(get_processing_options), converter: Converter = Depends(converter_dep)):
    return converter.run(req.text, normalization=options.normalization, filter_del=options.filter_del)
