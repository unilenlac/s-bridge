import os
import shutil
import uuid
import logging

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
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
    ref: Optional[str] = ""


class CollatexWitnessFileRequest(BaseModel):
    collection_url: str
    ref: str  # Required for this route


# ---------------------------------------------------------------------------
# Collate endpoint — fetch witnesses and proxy them to the CollateX Service
# ---------------------------------------------------------------------------

@router.post("/dts/process-and-collate",
    description=(
        "End-to-End NLP Collation Pipeline. This route orchestrates fetching XML resources from the DTS service, "
        "processes them through a CLTK/Stanza NLP engine (or similar) to convert text into deep-normalized token lists, "
        "and finally aligns them all together using the CollateX service. "
        "Workloads are executed securely in an asynchronous background job thread. Returns a Job ID to track pipeline status. "
        "Prototype route: http://ftsr-dev.unil.ch:8000/api/dts/v1/collection?id=s-bridge "
    ))
async def process_and_collate_resources(*,
    req: CollatexWitnessRequest,
    background_tasks: BackgroundTasks,
    options: ProcessingOptions = Depends(get_processing_options),
    converter: Converter = Depends(converter_dep),
    session: AsyncSession = Depends(get_session),
    http_client: http_client
):
    try:

        logger.info(f"Received collation request for collection URL: {req.collection_url} with ref: {req.ref}")
        # todo : Consider making this a dependency if it has state or external connections in the future. (no state as of 11.05.26)
        witness_service = WitnessService()

        collatex_client = CollatexClient(base_url=settings.collatex_api_base_url, http_client=http_client)
        stemmarest_client = StemmarestClient(base_url=settings.stemmarest_api_base_url, http_client=http_client)

        # Create Job
        job = Job(collection_url=req.collection_url, resources=[], ref=req.ref)
        session.add(job)
        await session.commit()
        await session.refresh(job)

        # Dispatch background worker
        background_tasks.add_task(
            run_collate_job,
            job_id=job.id,
            output_format="application/json",
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


@router.post("/dts/collate-to-file", response_class=FileResponse,
    description=(
        "Synchronous Collation Pipeline for a single section. Fetches XML resources from the DTS service for a specific reference, "
        "processes them through a CLTK/Stanza NLP engine to convert text into tokens, "
        "and aligns them using the CollateX service. The result is returned as a downloadable file. "
        "Example http://ftsr-dev.unil.ch:8000/api/dts/v1/collection?id=s-bridge"
    ))
async def collate_to_file(*,
    req: CollatexWitnessFileRequest,
    background_tasks: BackgroundTasks,
    output_format: str = Query("text/plain", description="Supported output format (application/json, application/tei+xml, application/graphml+xml, text/plain, image/svg+xml)"),
    options: ProcessingOptions = Depends(get_processing_options),
    converter: Converter = Depends(converter_dep),
    http_client: http_client
):
    try:
        logger.info(f"Received synchronous file collation request for collection URL: {req.collection_url} with ref: {req.ref}")
        
        witness_service = WitnessService()
        collatex_client = CollatexClient(base_url=settings.collatex_api_base_url, http_client=http_client)
        
        # We don't save to DB, but we need a unique ID for the directory paths
        temp_job_id = str(uuid.uuid4())
        
        # 1. Preprocess
        res, paths, collection_name, resources = await witness_service.preprocess_sections(
            req.collection_url, req.ref, temp_job_id, http_client, settings
        )
        
        if not res or not paths:
            raise HTTPException(status_code=400, detail="Failed to preprocess the specified reference. It might not exist in the collection.")
            
        path = paths[0]
        
        # 2. Analyse
        await witness_service.analyse_section(converter, options, http_client, path)
        ready_data = witness_service.load_prepared_section(path)
        
        # 3. Collate
        result = await collatex_client.collate(
            payload=ready_data.model_dump(by_alias=True, exclude_none=True),
            output_format=output_format
        )
        
        local_job_dir_name = f"{collection_name}_{temp_job_id}"
        
        # 4. Save result
        saved_path = witness_service.save_collation_result(
            collection_name=local_job_dir_name,
            ref_id=ready_data.ref_id,
            result=result,
            output_format=output_format,
            settings=settings
        )
        
        # 5. Cleanup task
        def cleanup_temp_dirs():
            try:
                post_collation_dir = os.path.join(settings.collation_dir, local_job_dir_name)
                pre_collation_dir = os.path.join(settings.output_dir, f"{collection_name}_{temp_job_id}")
                for directory in [post_collation_dir, pre_collation_dir]:
                    if os.path.exists(directory):
                        shutil.rmtree(directory)
                        logger.info(f"Cleanup: Deleted temp directory at {directory}")
            except Exception as e:
                logger.warning(f"Error cleaning up temp directories: {e}")
                
        background_tasks.add_task(cleanup_temp_dirs)
        
        return FileResponse(
            path=saved_path, 
            media_type="application/octet-stream", 
            filename=os.path.basename(saved_path)
        )
        
    except Exception as e:
        logger.error(f"Error during synchronous collation to file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dts/jobs", description="Fetch all jobs sorted in reverse chronological order with pagination.")
async def get_all_jobs(
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of jobs to return"),
    offset: int = Query(default=0, ge=0, description="Number of jobs to skip"),
    session: AsyncSession = Depends(get_session)
):
    stmt = select(Job).order_by(Job.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/dts/jobs/pending", description="Fetch all pending and processing jobs.")
async def get_pending_jobs(session: AsyncSession = Depends(get_session)):
    stmt = select(Job).where(Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]))
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/dts/jobs/failed", description="Fetch the last 5 failed jobs in reverse chronological order.")
async def get_failed_jobs(session: AsyncSession = Depends(get_session)):
    stmt = select(Job).where(Job.status == JobStatus.FAILED).order_by(Job.created_at.desc()).limit(5)
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
                collection_id_val = col_data.get("@id", "unknown_collection")
                collection_name = col_data.get("title") or collection_id_val
            else:
                collection_name = "unknown_collection"
                collection_id_val = "unknown_collection"
                
            post_collation_dir = os.path.join(settings.collation_dir, f"{collection_name}_{job.id}")
            pre_collation_dir = os.path.join(settings.output_dir, f"{collection_id_val}_{job.id}")
            
            for directory in [post_collation_dir, pre_collation_dir]:
                if os.path.exists(directory):
                    shutil.rmtree(directory)
                    logger.info(f"Cleanup on cancel: Deleted physical directory at {directory}")
                
            stmt = select(Tradition).where(Tradition.job_id == job.id)
            existing_tradition = (await session.execute(stmt)).scalar_one_or_none()
            if existing_tradition:
                await session.delete(existing_tradition)
                logger.info(f"Cleanup on cancel: Deleted existing Tradition DB record for job {job.id}")
                
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


