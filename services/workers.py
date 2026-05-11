import os
import uuid
import logging
from sqlmodel import select
from datetime import datetime
from core.config import Settings
from core.database import engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from models.schema import Job, JobStatus, Tradition
from sqlalchemy.orm.attributes import flag_modified

from httpx import AsyncClient

logger = logging.getLogger("s-bridge")

async def run_collate_job(
    job_id: uuid.UUID,
    output_format: str,
    options,
    converter,
    witness_service,
    collatex_client,
    stemmarest_client,
    collection_url: str,
    http_client: AsyncClient
):
    """
    Background worker that runs the collation task, tracking status to SQLite.
    """

    settings_cfg = Settings()
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

            sections_to_upload = []
            # preprocess from here get tmp file path then loop trough tmp file in pre_collation dir

            logger.info(f"Starting collation job {job_id} for collection '{collection_url}' with output format '{output_format}'")
            res, paths, collection_name, resources = await witness_service.preprocess_sections(collection_url, job.ref, str(job.id), http_client, settings_cfg)
            if not res:
                raise Exception("Preprocessing failed, cannot proceed with collation.")
                
            stemmarest_tradition_name = f"{collection_name}_{job.id}"

            for path in paths:
                # Check for cancellation before each large section
                await session.refresh(job)
                if job.status == JobStatus.CANCELLED.value:
                    logger.info(f"Job {job_id} was cancelled by user.")
                    break

                # The core NLP processing -> Collatex workflow
                await witness_service.analyse_section(converter, options, http_client, path)
                ready_data = witness_service.load_prepared_section(path)
                result = await collatex_client.collate(
                    payload=ready_data.model_dump(by_alias=True, exclude_none=True),
                    output_format=output_format
                )
                saved_path = witness_service.save_collation_result(
                    collection_name=stemmarest_tradition_name,
                    ref_id=ready_data.ref_id,
                    result=result,
                    output_format=output_format,
                    settings=settings_cfg
                )

                if output_format == "application/json":
                    sections_to_upload.append((ready_data.ref_id, saved_path))

            if job.status != JobStatus.CANCELLED.value:
            
                # settings_cfg is already instantiated above


                # Ensure the Stemmarest tradition exists for this collection
                trad_id = await stemmarest_client.get_or_create_tradition(
                    name=stemmarest_tradition_name, 
                    language=settings_cfg.language, 
                    direction="LR", 
                    is_public=False
                )

                # Append the newly created sections to the Stemmarest Tradition
                for section_name, file_path in sections_to_upload:
                    await stemmarest_client.upload_section(
                        trad_id=trad_id,
                        section_name=section_name,
                        file_path=file_path,
                        filetype="cxjson",
                        logger=logger
                    )

                collection_dir = os.path.join(settings_cfg.collation_dir, stemmarest_tradition_name)

                tradition = Tradition(
                    collection_id=stemmarest_tradition_name,
                    resources=resources,
                    number_of_included_sections=len(sections_to_upload),
                    result_path=collection_dir,
                    job_id=job.id,
                    collection_url=collection_url
                )
                
                session.add(tradition)

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
