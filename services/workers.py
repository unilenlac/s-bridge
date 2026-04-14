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
    collatex_client,
    stemmarest_client
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

            from core.config import Settings
            settings_cfg = Settings()
            
            # Ensure the Stemmarest tradition exists for this collection
            trad_id = await stemmarest_client.get_or_create_tradition(
                name=collection_name, 
                language=settings_cfg.language, 
                direction="LR", 
                is_public=False
            )

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

                # Append the newly created section to the Stemmarest Tradition
                if output_format == "application/json":
                    await stemmarest_client.upload_section(
                        trad_id=trad_id,
                        section_name=r,
                        file_path=saved_path,
                        filetype="cxjson"
                    )

                # Record or update the successfully collated artifact
                from sqlmodel import select
                stmt = select(Tradition).where(
                    Tradition.collection_id == collection_name,
                    Tradition.ref == r
                )
                existing_tradition = (await session.execute(stmt)).scalar_one_or_none()

                if existing_tradition:
                    from sqlalchemy.orm.attributes import flag_modified
                    
                    # Merge existing resources with new ones, avoiding duplicates
                    current_resources = list(existing_tradition.resources) if existing_tradition.resources else []
                    for r_res in resources:
                        if r_res not in current_resources:
                            current_resources.append(r_res)
                            
                    existing_tradition.resources = current_resources
                    existing_tradition.result_path = saved_path
                    existing_tradition.job_id = job.id
                    flag_modified(existing_tradition, "resources")
                    session.add(existing_tradition)
                else:
                    tradition = Tradition(
                        collection_id=collection_name,
                        resources=resources,
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
