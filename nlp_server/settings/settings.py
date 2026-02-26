from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    pipeline: str = "classical"  # Default pipeline (e.g., "modern" or "classical")
    language: str = "grc"