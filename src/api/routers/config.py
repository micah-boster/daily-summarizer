"""Config management API endpoints: read and write pipeline configuration."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.config import PipelineConfig, _format_validation_error, load_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["config"])

# Default config path (same as load_config default)
_DEFAULT_CONFIG_PATH = Path("config/config.yaml")

# Sensitive fields that should be redacted in GET responses.
# Each entry is a (section, field) tuple.
_SENSITIVE_FIELDS: list[tuple[str, str]] = [
    ("hubspot", "access_token"),
    ("notion", "token"),
]

_REDACTED = "\u2022\u2022\u2022\u2022\u2022\u2022"


def _redact(data: dict) -> dict:
    """Replace sensitive field values with bullet characters."""
    for section, field in _SENSITIVE_FIELDS:
        if section in data and field in data[section]:
            value = data[section][field]
            if value:  # Only redact non-empty values
                data[section][field] = _REDACTED
    return data


def _merge_redacted_secrets(incoming: dict, existing: dict) -> dict:
    """If the incoming payload has redacted placeholders, restore the real value."""
    for section, field in _SENSITIVE_FIELDS:
        if (
            section in incoming
            and field in incoming[section]
            and incoming[section][field] == _REDACTED
        ):
            # Restore the real value from the existing config
            if section in existing and field in existing[section]:
                incoming[section][field] = existing[section][field]
    return incoming


def _is_pipeline_running() -> bool:
    """Check if a pipeline run is currently active."""
    from src.config import load_config as _load

    config = _load()
    db_path = config.entity.db_path

    from src.entity.db import get_connection

    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT id FROM pipeline_runs WHERE status = 'running' LIMIT 1"
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _build_structured_errors(exc: ValidationError) -> list[dict]:
    """Build a list of {field, message} dicts from a Pydantic ValidationError."""
    errors = []
    for err in exc.errors():
        field_path = ".".join(str(p) for p in err["loc"])
        errors.append({"field": field_path, "message": err["msg"]})
    return errors


def _get_config_path() -> Path:
    """Return the config file path."""
    return _DEFAULT_CONFIG_PATH


@router.get("/config")
def get_config():
    """Return current pipeline config with sensitive fields redacted."""
    config = load_config()
    data = config.model_dump()
    return _redact(data)


@router.put("/config")
def update_config(body: dict):
    """Validate and write updated pipeline config atomically.

    Returns 409 if a pipeline run is active.
    Returns 422 with structured errors if validation fails.
    Returns 200 with redacted config on success.
    """
    # Block writes while pipeline is running
    if _is_pipeline_running():
        raise HTTPException(
            status_code=409,
            detail="Config locked while pipeline is running",
        )

    config_path = _get_config_path()

    # Load existing config for secret merging
    existing_data: dict = {}
    if config_path.exists():
        with open(config_path) as f:
            existing_data = yaml.safe_load(f) or {}

    # Merge redacted secrets back from existing config
    body = _merge_redacted_secrets(body, existing_data)

    # Validate through Pydantic
    try:
        validated = PipelineConfig(**body)
    except ValidationError as exc:
        formatted = _format_validation_error(exc)
        errors = _build_structured_errors(exc)
        return JSONResponse(
            status_code=422,
            content={"detail": formatted, "errors": errors},
        )

    # Atomic write: backup -> temp file -> rename
    data = validated.model_dump()

    # Create backup
    if config_path.exists():
        backup_path = config_path.with_suffix(".yaml.bak")
        shutil.copy2(config_path, backup_path)

    # Write to temp file then rename (atomic on same filesystem)
    fd, tmp_path = tempfile.mkstemp(
        dir=config_path.parent, suffix=".yaml.tmp"
    )
    try:
        with os.fdopen(fd, "w") as tmp_f:
            yaml.safe_dump(data, tmp_f, default_flow_style=False)
        os.rename(tmp_path, config_path)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    logger.info("Config updated and saved to %s", config_path)

    # Return the new config, redacted
    return _redact(data)
