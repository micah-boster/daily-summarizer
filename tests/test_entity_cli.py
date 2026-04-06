"""Tests for entity CLI command handlers."""

from __future__ import annotations

import argparse
import json
from unittest.mock import patch

import pytest

from src.config import make_test_config
from src.entity.cli import handle_entity_command


def _make_args(tmp_path: object, **kwargs) -> argparse.Namespace:
    """Create an argparse.Namespace with entity defaults."""
    defaults = {
        "config": "config/config.yaml",
        "command": "entity",
        "entity_command": None,
        "json_output": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


@pytest.fixture()
def mock_config(tmp_path):
    """Patch load_config to return a test config with tmp_path DB."""
    config = make_test_config(entity={"db_path": str(tmp_path / "test.db")})
    with patch("src.entity.cli.load_config", return_value=config):
        yield config


class TestEntityAdd:
    def test_creates_entity(self, tmp_path, mock_config, capsys) -> None:
        args = _make_args(tmp_path, entity_command="add", name="Affirm",
                          entity_type="partner", org_name=None)
        handle_entity_command(args)
        out = capsys.readouterr().out
        assert "Created partner: Affirm" in out

    def test_json_output(self, tmp_path, mock_config, capsys) -> None:
        args = _make_args(tmp_path, entity_command="add", name="Affirm",
                          entity_type="partner", org_name=None, json_output=True)
        handle_entity_command(args)
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "Affirm"
        assert data["entity_type"] == "partner"


class TestEntityList:
    def test_returns_entities(self, tmp_path, mock_config, capsys) -> None:
        # Add first
        args = _make_args(tmp_path, entity_command="add", name="Affirm",
                          entity_type="partner", org_name=None)
        handle_entity_command(args)

        # List
        args = _make_args(tmp_path, entity_command="list", entity_type=None)
        handle_entity_command(args)
        out = capsys.readouterr().out
        assert "Affirm" in out

    def test_filter_by_type(self, tmp_path, mock_config, capsys) -> None:
        # Add partner and person
        handle_entity_command(_make_args(tmp_path, entity_command="add",
                                         name="Affirm", entity_type="partner", org_name=None))
        handle_entity_command(_make_args(tmp_path, entity_command="add",
                                         name="Colin", entity_type="person", org_name=None))
        capsys.readouterr()  # clear

        # List only partners
        handle_entity_command(_make_args(tmp_path, entity_command="list",
                                         entity_type="partner"))
        out = capsys.readouterr().out
        assert "Affirm" in out
        assert "Colin" not in out

    def test_json_output(self, tmp_path, mock_config, capsys) -> None:
        handle_entity_command(_make_args(tmp_path, entity_command="add",
                                         name="Affirm", entity_type="partner", org_name=None))
        capsys.readouterr()

        handle_entity_command(_make_args(tmp_path, entity_command="list",
                                         entity_type=None, json_output=True))
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "Affirm"


class TestEntityShow:
    def test_displays_details(self, tmp_path, mock_config, capsys) -> None:
        handle_entity_command(_make_args(tmp_path, entity_command="add",
                                         name="Colin Roberts", entity_type="person", org_name=None))
        capsys.readouterr()

        handle_entity_command(_make_args(tmp_path, entity_command="show",
                                         name="Colin Roberts"))
        out = capsys.readouterr().out
        assert "Colin Roberts" in out
        assert "person" in out


class TestEntityRemove:
    def test_soft_deletes(self, tmp_path, mock_config, capsys) -> None:
        handle_entity_command(_make_args(tmp_path, entity_command="add",
                                         name="Affirm", entity_type="partner", org_name=None))
        capsys.readouterr()

        handle_entity_command(_make_args(tmp_path, entity_command="remove",
                                         name="Affirm"))
        out = capsys.readouterr().out
        assert "Removed partner: Affirm" in out

        # Verify it's gone from list
        handle_entity_command(_make_args(tmp_path, entity_command="list",
                                         entity_type=None))
        out = capsys.readouterr().out
        assert "Affirm" not in out


class TestEntityAlias:
    def test_add_alias(self, tmp_path, mock_config, capsys) -> None:
        handle_entity_command(_make_args(tmp_path, entity_command="add",
                                         name="Colin Roberts", entity_type="person", org_name=None))
        capsys.readouterr()

        args = _make_args(tmp_path, entity_command="alias", alias_command="add",
                          entity_name="Colin Roberts", alias="CR")
        handle_entity_command(args)
        out = capsys.readouterr().out
        assert "Added alias 'CR'" in out

    def test_list_aliases(self, tmp_path, mock_config, capsys) -> None:
        handle_entity_command(_make_args(tmp_path, entity_command="add",
                                         name="Colin Roberts", entity_type="person", org_name=None))
        handle_entity_command(_make_args(tmp_path, entity_command="alias",
                                         alias_command="add", entity_name="Colin Roberts", alias="CR"))
        capsys.readouterr()

        handle_entity_command(_make_args(tmp_path, entity_command="alias",
                                         alias_command="list", entity_name="Colin Roberts"))
        out = capsys.readouterr().out
        assert "CR" in out

    def test_remove_alias(self, tmp_path, mock_config, capsys) -> None:
        handle_entity_command(_make_args(tmp_path, entity_command="add",
                                         name="Colin Roberts", entity_type="person", org_name=None))
        handle_entity_command(_make_args(tmp_path, entity_command="alias",
                                         alias_command="add", entity_name="Colin Roberts", alias="CR"))
        capsys.readouterr()

        handle_entity_command(_make_args(tmp_path, entity_command="alias",
                                         alias_command="remove", alias="CR"))
        out = capsys.readouterr().out
        assert "Removed alias 'CR'" in out
