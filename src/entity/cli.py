"""CLI subparser and command handlers for entity management."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.config import load_config
from src.entity.repository import EntityRepository


def register_entity_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``entity`` subcommand with its sub-subparsers."""
    entity_parser = subparsers.add_parser("entity", help="Manage entities and aliases")
    entity_parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to config YAML file.",
    )
    entity_sub = entity_parser.add_subparsers(dest="entity_command")

    # entity add <name> --type partner|person
    add_p = entity_sub.add_parser("add", help="Create a new entity")
    add_p.add_argument("name", help="Entity name")
    add_p.add_argument("--type", dest="entity_type", required=True,
                       choices=["partner", "person"], help="Entity type")
    add_p.add_argument("--org", dest="org_name", default=None,
                       help="Organization name (resolves to entity ID)")
    add_p.add_argument("--json", dest="json_output", action="store_true",
                       help="Output as JSON")

    # entity list [--type partner|person]
    list_p = entity_sub.add_parser("list", help="List entities")
    list_p.add_argument("--type", dest="entity_type", default=None,
                        choices=["partner", "person"], help="Filter by type")
    list_p.add_argument("--json", dest="json_output", action="store_true",
                        help="Output as JSON")

    # entity show <name>
    show_p = entity_sub.add_parser("show", help="Show entity details")
    show_p.add_argument("name", help="Entity name")
    show_p.add_argument("--json", dest="json_output", action="store_true",
                        help="Output as JSON")

    # entity remove <name>
    remove_p = entity_sub.add_parser("remove", help="Soft-delete an entity")
    remove_p.add_argument("name", help="Entity name")

    # entity alias add/list/remove
    alias_p = entity_sub.add_parser("alias", help="Manage entity aliases")
    alias_sub = alias_p.add_subparsers(dest="alias_command")

    alias_add_p = alias_sub.add_parser("add", help="Add an alias for an entity")
    alias_add_p.add_argument("entity_name", help="Entity name")
    alias_add_p.add_argument("alias", help="Alias to add")

    alias_list_p = alias_sub.add_parser("list", help="List aliases for an entity")
    alias_list_p.add_argument("entity_name", help="Entity name")

    alias_remove_p = alias_sub.add_parser("remove", help="Remove an alias")
    alias_remove_p.add_argument("alias", help="Alias to remove")


def handle_entity_command(args: argparse.Namespace) -> None:
    """Dispatch entity subcommands."""
    config = load_config(Path(args.config))

    if not config.entity.enabled:
        print("Entity subsystem is disabled in config.", file=sys.stderr)
        sys.exit(1)

    try:
        with EntityRepository(config.entity.db_path) as repo:
            cmd = getattr(args, "entity_command", None)
            if cmd == "add":
                _cmd_add(repo, args)
            elif cmd == "list":
                _cmd_list(repo, args)
            elif cmd == "show":
                _cmd_show(repo, args)
            elif cmd == "remove":
                _cmd_remove(repo, args)
            elif cmd == "alias":
                _cmd_alias(repo, args)
            else:
                print("Usage: entity {add|list|show|remove|alias}", file=sys.stderr)
                sys.exit(1)
    except Exception as e:
        print("Entity database unavailable: %s" % e, file=sys.stderr)
        sys.exit(1)


# ------------------------------------------------------------------
# Command handlers
# ------------------------------------------------------------------


def _cmd_add(repo: EntityRepository, args: argparse.Namespace) -> None:
    try:
        entity = repo.add_entity(args.name, args.entity_type)
    except ValueError as e:
        print("Error: %s" % e, file=sys.stderr)
        sys.exit(1)

    if getattr(args, "json_output", False):
        print(entity.model_dump_json(indent=2))
    else:
        print("Created %s: %s (id: %s)" % (entity.entity_type, entity.name, entity.id))


def _cmd_list(repo: EntityRepository, args: argparse.Namespace) -> None:
    entities = repo.list_entities(entity_type=getattr(args, "entity_type", None))

    if getattr(args, "json_output", False):
        print(json.dumps([e.model_dump() for e in entities], indent=2, default=str))
        return

    if not entities:
        print("No entities found.")
        return

    # Table output
    header = "%-32s  %-10s  %s" % ("Name", "Type", "Created")
    print(header)
    print("-" * len(header))
    for e in entities:
        created = e.created_at[:10] if len(e.created_at) >= 10 else e.created_at
        print("%-32s  %-10s  %s" % (e.name, e.entity_type, created))


def _cmd_show(repo: EntityRepository, args: argparse.Namespace) -> None:
    entity = repo.get_by_name(args.name)
    if entity is None:
        print("Entity not found: %s" % args.name, file=sys.stderr)
        sys.exit(1)

    aliases = repo.list_aliases(entity.id)

    if getattr(args, "json_output", False):
        data = entity.model_dump()
        data["aliases"] = [a.alias for a in aliases]
        print(json.dumps(data, indent=2, default=str))
        return

    print("Name:    %s" % entity.name)
    print("Type:    %s" % entity.entity_type)
    print("ID:      %s" % entity.id)
    print("Created: %s" % entity.created_at)
    if aliases:
        print("Aliases: %s" % ", ".join(a.alias for a in aliases))
    else:
        print("Aliases: (none)")


def _cmd_remove(repo: EntityRepository, args: argparse.Namespace) -> None:
    entity = repo.get_by_name(args.name)
    if entity is None:
        print("Entity not found: %s" % args.name, file=sys.stderr)
        sys.exit(1)

    repo.remove_entity(entity.id)
    print("Removed %s: %s" % (entity.entity_type, entity.name))


def _cmd_alias(repo: EntityRepository, args: argparse.Namespace) -> None:
    alias_cmd = getattr(args, "alias_command", None)
    if alias_cmd == "add":
        entity = repo.get_by_name(args.entity_name)
        if entity is None:
            print("Entity not found: %s" % args.entity_name, file=sys.stderr)
            sys.exit(1)
        try:
            alias = repo.add_alias(entity.id, args.alias)
            print("Added alias '%s' for %s" % (alias.alias, entity.name))
        except ValueError as e:
            print("Error: %s" % e, file=sys.stderr)
            sys.exit(1)

    elif alias_cmd == "list":
        entity = repo.get_by_name(args.entity_name)
        if entity is None:
            print("Entity not found: %s" % args.entity_name, file=sys.stderr)
            sys.exit(1)
        aliases = repo.list_aliases(entity.id)
        if not aliases:
            print("No aliases for %s" % entity.name)
        else:
            for a in aliases:
                print("  %s" % a.alias)

    elif alias_cmd == "remove":
        removed = repo.remove_alias(args.alias)
        if removed:
            print("Removed alias '%s'" % args.alias)
        else:
            print("Alias not found: %s" % args.alias, file=sys.stderr)
            sys.exit(1)

    else:
        print("Usage: entity alias {add|list|remove}", file=sys.stderr)
        sys.exit(1)
