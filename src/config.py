from __future__ import annotations

import os
from pathlib import Path

import yaml


def load_config(config_path: Path | None = None) -> dict:
    """Load pipeline configuration from YAML with environment variable overrides.

    Args:
        config_path: Path to YAML config file. Defaults to config/config.yaml.

    Returns:
        Configuration dictionary. Empty dict if file doesn't exist.
    """
    if config_path is None:
        config_path = Path("config/config.yaml")

    config: dict = {}
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

    # Ensure nested dicts exist for env var overrides
    config.setdefault("pipeline", {})
    config.setdefault("calendars", {})
    config.setdefault("hubspot", {})

    # Environment variable overrides
    if tz := os.environ.get("SUMMARIZER_TIMEZONE"):
        config["pipeline"]["timezone"] = tz

    if cal_ids := os.environ.get("SUMMARIZER_CALENDAR_IDS"):
        config["calendars"]["ids"] = [cid.strip() for cid in cal_ids.split(",")]

    if output_dir := os.environ.get("SUMMARIZER_OUTPUT_DIR"):
        config["pipeline"]["output_dir"] = output_dir

    return config
