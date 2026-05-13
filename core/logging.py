import logging
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import Settings

FORMATTER = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# Third-party loggers that are known to be noisy in production
_THIRD_PARTY_LOGGERS = ["stanza", "cltk", "httpx", "httpcore"]


def setup_logging(settings: "Settings | None" = None) -> logging.Logger:
    """Configure the root s-bridge logger.

    DEV (default): logs to stdout at DEBUG level.
    PROD: logs to a rotating file at INFO level (10 MB, 5 backups).
          Third-party library loggers (stanza, cltk, …) are also
          redirected to the same file so they don't leak to stdout.
          Falls back to stdout if the log file cannot be opened.
    """
    logger = logging.getLogger("s-bridge")
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        return logger

    is_prod = settings is not None and settings.environment.value == "PROD"

    if is_prod and settings.log_file is not None:
        log_path = settings.log_file
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            handler: logging.Handler = RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
                encoding="utf-8",
            )
            handler.setLevel(logging.INFO)
            handler.setFormatter(FORMATTER)
            logger.addHandler(handler)

            # Silence any StreamHandlers on the root logger that uvicorn
            # or Python's logging machinery may have already installed.
            root = logging.getLogger()
            for h in list(root.handlers):
                if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler):
                    root.removeHandler(h)
            root.addHandler(handler)
            root.setLevel(logging.INFO)

            # Redirect known noisy third-party loggers explicitly so they
            # write to our file and stop propagating to any stray stdout handler.
            for name in _THIRD_PARTY_LOGGERS:
                lib_logger = logging.getLogger(name)
                lib_logger.handlers = [handler]
                lib_logger.propagate = False
                lib_logger.setLevel(logging.INFO)

            logger.info("PROD mode: logging to file '%s'", log_path)
            return logger

        except OSError as exc:
            # Cannot write to log file – fall back gracefully to stdout
            handler = logging.StreamHandler()
            handler.setLevel(logging.DEBUG)
            logger.warning(
                "PROD mode: could not open log file '%s' (%s). Falling back to stdout.",
                log_path, exc,
            )
    else:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)

    handler.setFormatter(FORMATTER)
    logger.addHandler(handler)
    return logger
