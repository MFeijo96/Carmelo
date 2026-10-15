import json
import logging
from typing import Any

logger = logging.getLogger("home_financial")


def configure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def confidence_bucket(confidence: float | None) -> str:
    if confidence is None:
        return "none"
    if confidence < 0.5:
        return "lt_0.50"
    if confidence < 0.7:
        return "0.50_0.69"
    if confidence < 0.9:
        return "0.70_0.89"
    return "gte_0.90"


def log_event(event: str, **fields: float | str | bool | None) -> None:
    """Emit one structured line; callers pass only counts, codes, and timings, never user text."""
    payload: dict[str, Any] = {"event": event, **fields}
    logger.info(json.dumps(payload, sort_keys=True, ensure_ascii=False))
