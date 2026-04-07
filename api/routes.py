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
from services.workers import run_collate_job
from core.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import Job, JobStatus, Tradition
import uuid
from fastapi import BackgroundTasks
from core.config import Settings
from sqlmodel import select

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
# Collate endpoint — fetch witnesses and proxy them to the CollateX Service
# ---------------------------------------------------------------------------

@router.post("/dts/collate",
    description=(
        "Proxy to the CollateX service. Submits a job to run in the background "
        "and immediately returns a job ID to track status."
    ))
async def collate_resources(
    req: CollatexWitnessRequest,
    background_tasks: BackgroundTasks,
    output_format: str = Query("application/json", description="Output format"),
    options: ProcessingOptions = Depends(get_processing_options),
    converter: Converter = Depends(converter_dep),
    session: AsyncSession = Depends(get_session)
):
    try:
        # Identify refs
        if req.ref:
            refs = [req.ref]
        else:
            members = await dts_client.get_members(req.resources[0])
            refs = [m["identifier"] for m in members]

        collection_name = await witness_service.fetcher.get_collection_name(req.resources[0])

        # Create Job
        job = Job(resource_id=collection_name, ref=req.ref)
        session.add(job)
        await session.commit()
        await session.refresh(job)

        # Dispatch background worker
        background_tasks.add_task(
            run_collate_job,
            job_id=job.id,
            collection_name=collection_name,
            refs=refs,
            resources=req.resources,
            output_format=output_format,
            options=options,
            converter=converter,
            witness_service=witness_service,
            collatex_client=collatex_client
        )

        return {
            "job_id": str(job.id),
            "status": job.status,
            "message": "Collation job started in the background."
        }
        
    except Exception as e:
        logger.error(f"Error starting collate job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dts/jobs/{job_id}", description="Fetch the status of a specific job.")
async def get_job_status(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.put("/dts/jobs/{job_id}/cancel", description="Cancel a pending or processing job.")
async def cancel_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status in [JobStatus.PENDING.value, JobStatus.PROCESSING.value]:
        job.status = JobStatus.CANCELLED.value
        session.add(job)
        await session.commit()
        return {"status": job.status, "message": "Job cancelled."}
    
    raise HTTPException(status_code=400, detail=f"Cannot cancel job in state: {job.status}")


@router.get("/dts/traditions", description="List all successfully completed traditions.")
async def get_traditions(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Tradition))
    return result.scalars().all()


