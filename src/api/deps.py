"""FastAPI dependency injection for config, entity repo, and summary reader."""

from __future__ import annotations

from typing import Generator

from fastapi import HTTPException

from src.api.services.rollup_reader import RollupReader
from src.api.services.summary_reader import SummaryReader
from src.config import load_config, PipelineConfig
from src.entity.repository import EntityRepository


def get_config() -> PipelineConfig:
    """Load and return the pipeline configuration.

    Catches SystemExit from load_config's validation failure path
    and converts it to a 500 HTTP error.
    """
    try:
        return load_config()
    except SystemExit:
        raise HTTPException(status_code=500, detail="Invalid pipeline configuration")


def get_entity_repo() -> Generator[EntityRepository, None, None]:
    """Provide an EntityRepository scoped to a single request."""
    config = get_config()
    repo = EntityRepository(config.entity.db_path)
    try:
        repo.connect()
        yield repo
    finally:
        repo.close()


def get_summary_reader() -> SummaryReader:
    """Provide a SummaryReader configured from pipeline settings."""
    config = get_config()
    return SummaryReader(output_dir=config.pipeline.output_dir)


def get_rollup_reader() -> RollupReader:
    """Provide a RollupReader configured from pipeline settings."""
    config = get_config()
    return RollupReader(output_dir=config.pipeline.output_dir)
