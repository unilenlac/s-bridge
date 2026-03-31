import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    pipeline: str = "classical"  # Default pipeline (e.g., "modern" or "classical")
    language: str = "grc"
    tag_config: Optional[str] = None  # Path to a JSON tag dictionary file
    dts_api_base_url: str = "http://ftsr-dev.unil.ch:8000"

    def load_tag_dictionary(self) -> Dict[str, Any]:
        """Load and validate a tag dictionary from the JSON file at ``tag_config``.

        If no ``tag_config`` is provided, it falls back to the default
        ``nlp_server/utils/enlac_tags.json`` shipped with the project.

        Raises:
            FileNotFoundError: If the configured (or default) path does not exist.
            ValueError: If the JSON is malformed or structurally invalid.
        """
        path_str = self.tag_config
        if path_str is None:
            # Absolute path to the default reference file
            path_str = str(Path(__file__).parent.parent / "utils" / "enlac_tags.json")

        path = Path(path_str)
        if not path.is_file():
            raise FileNotFoundError(
                f"Tag config file not found: '{path_str}'."
            )

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Tag config file '{self.tag_config}' contains invalid JSON: {exc}"
            ) from exc

        _validate_tag_dictionary(raw, str(path))
        logger.info("Loaded custom tag dictionary from '%s' (%d tags)", path, len(raw))
        return raw


def _validate_tag_dictionary(data: Any, source: str) -> None:
    """Validate the top-level structure of a tag dictionary.
    """
    if not isinstance(data, dict):
        raise ValueError(
            f"Tag config '{source}': expected a JSON object at the top level, got {type(data).__name__}."
        )

    for tag_name, tag_cfg in data.items():
        if not isinstance(tag_name, str):
            raise ValueError(
                f"Tag config '{source}': tag names must be strings, got {type(tag_name).__name__}."
            )
        if not isinstance(tag_cfg, dict):
            raise ValueError(
                f"Tag config '{source}': config for tag '{tag_name}' must be a dict, "
                f"got {type(tag_cfg).__name__}."
            )