import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker

from core.config import Settings

logger = logging.getLogger(__name__)

settings = Settings()

# Ensure the directory exists if using sqlite
if "sqlite" in settings.database_url:
    # Extracts the file path from 'sqlite+aiosqlite:///data/s_bridge.db'
    db_path = settings.database_url.split("///")[-1]
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
        # Create empty file immediately to avoid directory issues with Alembic or SQLAlchemy
        open(db_path, "a").close()

engine = create_async_engine(
    settings.database_url,
    echo=False,  # Set to True for SQL queries logging
    future=True,
)


async def get_session() -> AsyncSession:
    """
    FastAPI dependency that provides an SQLAlchemy AsyncSession.
    """
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
