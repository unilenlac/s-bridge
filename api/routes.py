import uuid
import logging

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from urllib.parse import urlparse

from core.interfaces import Converter
from api.dependencies import converter_dep, get_processing_options, ProcessingOptions, http_client
from models.tokenization import Token
from clients.collatex_client import CollatexClient
from clients.stemmarest_client import StemmarestClient
from services.witness_service import WitnessService
from services.workers import run_collate_job
from core.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from models.schema import Job, JobStatus, Tradition
from fastapi import BackgroundTasks
from core.config import Settings
from sqlmodel import select

logger = logging.getLogger('s-bridge')

# APIRouter acts as a mini FastAPI application to structure the routes.
router = APIRouter()

settings = Settings()

# collatex_client and stemmarest_client are instantiated per-route to utilize the global http_client pool

class ConvertRequest(BaseModel):
    text: str

@router.post("/convert", response_model=list[Token],
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
    description="Convert input text using the specified converter")
async def convert(req: ConvertRequest,
    options: ProcessingOptions = Depends(get_processing_options),
    converter: Converter = Depends(converter_dep)):
    return converter.run(req.text, normalization=options.normalization, filter_del=options.filter_del)

# ---------------------------------------------------------------------------
# Witness endpoint — fetch multiple witnesses for Collatex (optional ref)
# ---------------------------------------------------------------------------

class CollatexWitnessRequest(BaseModel):
    collection_url: str
    ref: Optional[str] = None


# ---------------------------------------------------------------------------
# Collate endpoint — fetch witnesses and proxy them to the CollateX Service
# ---------------------------------------------------------------------------

@router.post("/dts/process-and-collate",
    description=(
        "End-to-End NLP Collation Pipeline. This route orchestrates fetching XML resources from the DTS service, "
        "processes them through a CLTK/Stanza NLP engine (or similar) to convert text into deep-normalized token lists, "
        "and finally aligns them all together using the CollateX service. "
        "Workloads are executed securely in an asynchronous background job thread. Returns a Job ID to track pipeline status."
    ))
async def process_and_collate_resources(*,
    req: CollatexWitnessRequest,
    background_tasks: BackgroundTasks,
    output_format: str = Query("application/json", description="Output format"),
    options: ProcessingOptions = Depends(get_processing_options),
    converter: Converter = Depends(converter_dep),
    session: AsyncSession = Depends(get_session),
    http_client: http_client
):
    try:

        logger.info(f"Received collation request for collection URL: {req.collection_url} with ref: {req.ref}")
        # todo : Consider making this a dependency if it has state or external connections in the future.
        witness_service = WitnessService()

        collatex_client = CollatexClient(base_url=settings.collatex_api_base_url, http_client=http_client)
        stemmarest_client = StemmarestClient(base_url=settings.stemmarest_api_base_url, http_client=http_client)

        # Create Job
        job = Job(collection_url=req.collection_url, resources=["witnesses"], ref=req.ref)
        session.add(job)
        await session.commit()
        await session.refresh(job)

        # Dispatch background worker
        background_tasks.add_task(
            run_collate_job,
            job_id=job.id,
            output_format=output_format,
            options=options,
            converter=converter,
            witness_service=witness_service,
            collatex_client=collatex_client,
            stemmarest_client=stemmarest_client,
            collection_url=req.collection_url,
            http_client=http_client
        )

        return {
            "job_id": str(job.id),
            "status": job.status,
            "message": "Collation job started in the background."
        }
        
    except Exception as e:
        logger.error(f"Error starting collate job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dts/jobs/pending", description="Fetch all pending and processing jobs.")
async def get_pending_jobs(session: AsyncSession = Depends(get_session)):
    stmt = select(Job).where(Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]))
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/dts/jobs/{job_id}", description="Fetch the status of a specific job.")
async def get_job_status(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.put("/dts/jobs/{job_id}/cancel", description="Cancel a pending or processing job and clear its associated files.")
async def cancel_job(
    job_id: uuid.UUID, 
    session: AsyncSession = Depends(get_session),
    http_client: http_client = None
):
    import os
    import shutil
    from sqlmodel import select
    
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status in [JobStatus.PENDING.value, JobStatus.PROCESSING.value]:
        job.status = JobStatus.CANCELLED.value
        session.add(job)
        
        # Cleanup: delete the collection folders and any existing Tradition for this collection
        try:
            # We fetch the collection title to determine the folder name
            res = await http_client.get(job.collection_url, follow_redirects=True)
            if res.status_code == 200:
                col_data = res.json()
                collection_name = col_data.get("title") or col_data.get("@id")
            else:
                collection_name = "unknown_collection"
                
            post_collation_dir = os.path.join(settings.collation_dir, collection_name)
            pre_collation_dir = os.path.join(settings.output_dir, collection_name)
            
            for directory in [post_collation_dir, pre_collation_dir]:
                if os.path.exists(directory):
                    shutil.rmtree(directory)
                    logger.info(f"Cleanup on cancel: Deleted physical directory at {directory}")
                
            stmt = select(Tradition).where(Tradition.collection_url == job.collection_url)
            existing_tradition = (await session.execute(stmt)).scalar_one_or_none()
            if existing_tradition:
                await session.delete(existing_tradition)
                logger.info(f"Cleanup on cancel: Deleted existing Tradition DB record for {job.collection_url}")
                
        except Exception as e:
            logger.warning(f"Cleanup on cancel encountered an error, some files may remain: {e}")
            
        await session.commit()
        return {"status": job.status, "message": "Job cancelled and associated files/records cleaned up."}
    
    raise HTTPException(status_code=400, detail=f"Cannot cancel job in state: {job.status}")


@router.get("/dts/traditions", description="List all successfully completed traditions.")
async def get_traditions(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Tradition))
    return result.scalars().all()


@router.delete("/dts/traditions/{tradition_id}", description="Safely delete a Tradition's database record and physical disk directory.")
async def delete_tradition(tradition_id: int, session: AsyncSession = Depends(get_session)):
    import os
    import shutil
    tradition = await session.get(Tradition, tradition_id)
    if not tradition:
        raise HTTPException(status_code=404, detail="Tradition not found in database.")
    
    # Safely remove the directory from the disk if it exists
    try:
        if os.path.exists(tradition.result_path):
            shutil.rmtree(tradition.result_path)
            logger.info(f"Deleted physical Tradition directory at {tradition.result_path}")
    except Exception as e:
        logger.warning(f"Could not delete physical directory at {tradition.result_path}. It may already be deleted. Error: {e}")

    # Remove the DB record
    await session.delete(tradition)
    await session.commit()
    
    return {"status": "success", "message": f"Deleted tradition ID {tradition_id}"}


