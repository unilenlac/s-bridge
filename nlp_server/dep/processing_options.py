from fastapi import Query
from pydantic import BaseModel

class ProcessingOptions(BaseModel):
    normalization: str
    filter_del: bool

async def get_processing_options(
    normalization: str = Query("lemma+pos", description="Token normalization string. Options: lemma+pos, lemma, text, original"),
    filter_del: bool = Query(True, description="Filter out tokens that are marked as deleted")
) -> ProcessingOptions:
    return ProcessingOptions(normalization=normalization, filter_del=filter_del)