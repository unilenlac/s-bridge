import logging
from typing import List
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from core.database import engine
from models.schema import Job, JobStatus, Tradition

logger = logging.getLogger(__name__)

async def run_collate_job(
    job_id: uuid.UUID,
    collection_name: str,
    refs: List[str],
    resources: List[str],
    output_format: str,
    options,
    converter,
    witness_service,
    collatex_client
):
    """
    Background worker that runs the collation task, tracking status to SQLite.
    """
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        job = await session.get(Job, job_id)
        if not job:
            logger.error(f"Job {job_id} not found in DB.")
            return

        try:
            job.status = JobStatus.PROCESSING.value
            session.add(job)
            await session.commit()

            for r in refs:
                # Check for cancellation before each large section
                await session.refresh(job)
                if job.status == JobStatus.CANCELLED.value:
                    logger.info(f"Job {job_id} was cancelled by user.")
                    break

                # The core NLP processing -> Collatex workflow
                path = await witness_service.prepare_section_if_needed(resources, r, converter, options)
                ready_data = witness_service.load_prepared_section(path)
                result = await collatex_client.collate(
                    payload=ready_data.model_dump(by_alias=True, exclude_none=True),
                    output_format=output_format
                )
                saved_path = witness_service.save_collation_result(
                    collection_name=collection_name,
                    ref_id=r,
                    result=result,
                    output_format=output_format
                )

                # Record the successfully collated artifact
                tradition = Tradition(
                    resource_id=collection_name,
                    ref=r,
                    result_path=saved_path,
                    job_id=job.id
                )
                session.add(tradition)
                await session.commit()

            if job.status != JobStatus.CANCELLED.value:
                job.status = JobStatus.COMPLETED.value
                session.add(job)
                await session.commit()
                logger.info(f"Collation job {job_id} successfully completed for collection '{collection_name}'.")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            job.status = JobStatus.FAILED.value
            job.error_message = str(e)
            session.add(job)
            await session.commit()
