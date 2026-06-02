import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from enum import Enum
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class PipelineEnum(str, Enum):
    classical = "classical"
    modern = "modern"


class EnvironmentEnum(str, Enum):
    dev = "DEV"
    prod = "PROD"


class LanguageEnum(str, Enum):
    lati1261 = "lati1261"  # Latin
    anci1242 = "anci1242"  # Ancient Greek
    chur1257 = "chur1257"  # Church Slavonic
    oldf1239 = "oldf1239"  # Old French
    goth1244 = "goth1244"  # Gothic
    lite1248 = "lite1248"  # Literary Chinese
    olde1238 = "olde1238"  # Old English
    otto1234 = "otto1234"  # Ottoman Turkish
    clas1256 = "clas1256"  # Classical Armenian
    copt1239 = "copt1239"  # Coptic
    oldr1238 = "oldr1238"  # Old Russian (Old East Slavic)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    pipeline: PipelineEnum = PipelineEnum.classical
    language: LanguageEnum = LanguageEnum.anci1242
    tag_config: Optional[str] = None  # Path to a JSON tag dictionary file
    collatex_api_base_url: str = "http://ftsr-dev.unil.ch:7369"
    stemmarest_api_base_url: str = "http://ftsr-dev.unil.ch:7070/stemmarest/api"
    nlp_analysis_dir: Path = Path("/tmp/s-bridge/pre_collation")
    collation_dir: Path = Path("/tmp/s-bridge/post_collation")
    environment: EnvironmentEnum = EnvironmentEnum.dev
    log_file: Optional[Path] = Path("/var/log/s-bridge/s-bridge.log")

    @property
    def database_url(self) -> str:
        return "sqlite+aiosqlite:///data/s_bridge.db"

    @model_validator(mode="after")
    def validate_tag_config(self) -> "Settings":
        self.load_tag_dictionary()
        return self

    @field_validator("nlp_analysis_dir", "collation_dir")
    @classmethod
    def ensure_posix_path(cls, v: Path) -> Path:
        if not v.is_absolute():
            raise ValueError(f"Path '{v}' must be an absolute POSIX path.")
        return v


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
            raise ValueError(
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