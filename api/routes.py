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
from clients.stemmarest_client import StemmarestClient
from services.witness_service import WitnessService
from services.workers import run_collate_job
from core.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from models.schema import Job, JobStatus, Tradition
import uuid
from fastapi import BackgroundTasks
from core.config import Settings
from sqlmodel import select

# APIRouter acts as a mini FastAPI application to structure the routes.
router = APIRouter()

settings = Settings()
collatex_client = CollatexClient(base_url=settings.collatex_api_base_url)
stemmarest_client = StemmarestClient(base_url=settings.stemmarest_api_base_url)


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
async def process_and_collate_resources(
    req: CollatexWitnessRequest,
    background_tasks: BackgroundTasks,
    output_format: str = Query("application/json", description="Output format"),
    options: ProcessingOptions = Depends(get_processing_options),
    converter: Converter = Depends(converter_dep),
    session: AsyncSession = Depends(get_session)
):
    try:
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(req.collection_url)
        base_path = parsed_url.path.split('/collection')[0]
        dts_base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{base_path}"
        
        query_params = parse_qs(parsed_url.query)
        collection_id = query_params.get("id", [""])[0]
        
        if not collection_id:
            raise ValueError(f"Collection ID could not be extracted from {req.collection_url}")
            
        dts_client = DTSClient(base_url=dts_base_url)
        witness_service = WitnessService(fetcher=dts_client)

        collection_name, resources = await dts_client.get_collection_details(collection_id)
        if not resources:
            raise ValueError(f"No resources found for collection {collection_id}")

        # Identify refs
        if req.ref:
            refs = [req.ref]
        else:
            members = await dts_client.get_members(resources[0])
            refs = [m["identifier"] for m in members]

        # Create Job
        job = Job(collection_id=collection_id, dts_base_url=dts_base_url, resources=resources, ref=req.ref)
        session.add(job)
        await session.commit()
        await session.refresh(job)

        # Dispatch background worker
        background_tasks.add_task(
            run_collate_job,
            job_id=job.id,
            collection_id=collection_id,
            collection_name=collection_name,
            refs=refs,
            resources=resources,
            output_format=output_format,
            options=options,
            converter=converter,
            witness_service=witness_service,
            collatex_client=collatex_client,
            stemmarest_client=stemmarest_client,
            dts_base_url=dts_base_url
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


@router.put("/dts/jobs/{job_id}/cancel", description="Cancel a pending or processing job and clear its associated files.")
async def cancel_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
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
            dts_client = DTSClient(base_url=job.dts_base_url)
            collection_name, _ = await dts_client.get_collection_details(job.collection_id)
            post_collation_dir = os.path.join(settings.collation_dir, collection_name)
            pre_collation_dir = os.path.join(settings.output_dir, collection_name)
            
            for directory in [post_collation_dir, pre_collation_dir]:
                if os.path.exists(directory):
                    shutil.rmtree(directory)
                    logger.info(f"Cleanup on cancel: Deleted physical directory at {directory}")
                
            stmt = select(Tradition).where(Tradition.collection_id == job.collection_id)
            existing_tradition = (await session.execute(stmt)).scalar_one_or_none()
            if existing_tradition:
                await session.delete(existing_tradition)
                logger.info(f"Cleanup on cancel: Deleted existing Tradition DB record for {job.collection_id}")
                
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


