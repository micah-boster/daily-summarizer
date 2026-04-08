"""CLI subparser and command handlers for entity management."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
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

    # entity list [--type partner|person] [--sort active|mentions|name]
    list_p = entity_sub.add_parser("list", help="List entities with enriched stats")
    list_p.add_argument("--type", dest="entity_type", default=None,
                        choices=["partner", "person"], help="Filter by type")
    list_p.add_argument("--sort", dest="sort_by", default="active",
                        choices=["active", "mentions", "name"],
                        help="Sort by: active (default), mentions, name")
    list_p.add_argument("--json", dest="json_output", action="store_true",
                        help="Output as JSON")

    # entity show <name> [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--all]
    show_p = entity_sub.add_parser("show", help="Show entity scoped activity view")
    show_p.add_argument("name", help="Entity name")
    show_p.add_argument("--from", dest="from_date", type=date.fromisoformat, default=None,
                        help="Start date (YYYY-MM-DD)")
    show_p.add_argument("--to", dest="to_date", type=date.fromisoformat, default=None,
                        help="End date (YYYY-MM-DD)")
    show_p.add_argument("--all", dest="show_all", action="store_true", default=False,
                        help="Show all activity (no date filter)")
    show_p.add_argument("--json", dest="json_output", action="store_true",
                        help="Output as JSON")

    # entity report <name> [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--output-dir DIR]
    report_p = entity_sub.add_parser("report", help="Generate per-entity markdown report")
    report_p.add_argument("name", help="Entity name")
    report_p.add_argument("--from", dest="from_date", type=date.fromisoformat, default=None,
                          help="Start date (YYYY-MM-DD)")
    report_p.add_argument("--to", dest="to_date", type=date.fromisoformat, default=None,
                          help="End date (YYYY-MM-DD)")
    report_p.add_argument("--output-dir", dest="output_dir", default=None,
                          help="Output directory (default: output/entities)")

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

    # entity review [--limit N] [--type partner|person]
    review_p = entity_sub.add_parser("review", help="Review merge proposals interactively")
    review_p.add_argument("--limit", type=int, default=10,
                          help="Max proposals per session (default 10)")
    review_p.add_argument("--type", dest="entity_type", default=None,
                          choices=["partner", "person"], help="Filter by entity type")

    # entity split <name>
    split_p = entity_sub.add_parser("split", help="Reverse a merge and restore an entity")
    split_p.add_argument("name", help="Name of the entity to split/restore")

    # entity backfill --from YYYY-MM-DD --to YYYY-MM-DD [--force]
    backfill_p = entity_sub.add_parser("backfill", help="Backfill entity registry from historical data")
    backfill_p.add_argument(
        "--from", dest="from_date", type=date.fromisoformat, required=True,
        help="Start date (YYYY-MM-DD)",
    )
    backfill_p.add_argument(
        "--to", dest="to_date", type=date.fromisoformat, required=True,
        help="End date (YYYY-MM-DD)",
    )
    backfill_p.add_argument(
        "--force", action="store_true", default=False,
        help="Re-process already-scanned days",
    )


def handle_entity_command(args: argparse.Namespace) -> None:
    """Dispatch entity subcommands."""
    config = load_config(Path(args.config))

    if not config.entity.enabled:
        print("Entity subsystem is disabled in config.", file=sys.stderr)
        sys.exit(1)

    cmd = getattr(args, "entity_command", None)

    # Backfill manages its own connections
    if cmd == "backfill":
        _cmd_backfill(config, args)
        return

    try:
        with EntityRepository(config.entity.db_path) as repo:
            if cmd == "add":
                _cmd_add(repo, args)
            elif cmd == "list":
                _cmd_list(repo, args)
            elif cmd == "show":
                _cmd_show(repo, args)
            elif cmd == "report":
                _cmd_report(repo, args, config)
            elif cmd == "remove":
                _cmd_remove(repo, args)
            elif cmd == "alias":
                _cmd_alias(repo, args)
            elif cmd == "review":
                _cmd_review(repo, args)
            elif cmd == "split":
                _cmd_split(repo, args)
            else:
                print("Usage: entity {add|list|show|report|remove|alias|review|split|backfill}", file=sys.stderr)
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
    from src.entity.views import get_enriched_entity_list

    sort_by = getattr(args, "sort_by", "active")
    entities = get_enriched_entity_list(
        repo, entity_type=getattr(args, "entity_type", None), sort_by=sort_by
    )

    if getattr(args, "json_output", False):
        print(json.dumps([e.model_dump() for e in entities], indent=2, default=str))
        return

    if not entities:
        print("No entities found.")
        return

    # Enriched table output
    header = "%-28s  %-8s  %8s  %8s  %-12s" % (
        "Name", "Type", "Mentions", "Commits", "Last Active"
    )
    print(header)
    print("-" * len(header))
    for e in entities:
        last = e.last_active_date[:10] if e.last_active_date else "\u2014"
        print(
            "%-28s  %-8s  %8d  %8d  %-12s"
            % (e.name[:28], e.entity_type, e.mention_count, e.commitment_count, last)
        )


def _cmd_show(repo: EntityRepository, args: argparse.Namespace) -> None:
    from src.entity.views import get_entity_scoped_view

    show_all = getattr(args, "show_all", False)
    from_date = None if show_all else getattr(args, "from_date", None)
    to_date = None if show_all else getattr(args, "to_date", None)

    try:
        view = get_entity_scoped_view(repo, args.name, from_date, to_date)
    except ValueError as e:
        print("Error: %s" % e, file=sys.stderr)
        sys.exit(1)

    if getattr(args, "json_output", False):
        print(view.model_dump_json(indent=2))
        return

    # Terminal output
    print("Entity: %s (%s)" % (view.entity_name, view.entity_type))
    print("Period: %s to %s" % (view.from_date or "all time", view.to_date or "today"))
    print()

    # Open commitments section (highlighted)
    if view.open_commitments:
        print("=== OPEN COMMITMENTS ===")
        for c in view.open_commitments:
            print("  [%s] %s" % (c.source_date, c.context_snippet or "(no details)"))
        print()

    # Highlights section (top 5 significant items)
    if view.highlights:
        print("--- Highlights ---")
        for h in view.highlights:
            label = h.source_type.upper()
            print(
                "  [%s] %s: %s"
                % (h.source_date, label, h.context_snippet or "(no snippet)")
            )
        print()

    # Full activity grouped by date
    if view.activity_by_date:
        print("--- Activity ---")
        for date_group in view.activity_by_date:
            print("\n  %s" % date_group["date"])
            for item in date_group["items"]:
                label = item.source_type.upper()
                print("    [%s] %s" % (label, item.context_snippet or "(no snippet)"))
    elif not view.open_commitments and not view.highlights:
        print("No activity found for %s in this period." % view.entity_name)
        print("Try: entity show %s --all" % args.name)


def _cmd_report(repo: EntityRepository, args: argparse.Namespace, config) -> None:
    from src.entity.views import generate_entity_report

    output_dir = getattr(args, "output_dir", None)
    if output_dir is None:
        output_dir = str(Path(config.pipeline.output_dir) / "entities")

    try:
        path = generate_entity_report(
            repo=repo,
            entity_name=args.name,
            from_date=getattr(args, "from_date", None),
            to_date=getattr(args, "to_date", None),
            output_dir=output_dir,
        )
        print("Report generated: %s" % path)
    except ValueError as e:
        print("Error: %s" % e, file=sys.stderr)
        sys.exit(1)


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


def _cmd_review(repo: EntityRepository, args: argparse.Namespace) -> None:
    from src.entity.merger import execute_merge, generate_proposals

    proposals = generate_proposals(
        repo,
        entity_type=getattr(args, "entity_type", None),
        limit=getattr(args, "limit", 10),
    )

    if not proposals:
        print("No merge proposals found.")
        return

    total = len(proposals)
    print("Found %d merge proposal(s). Reviewing...\n" % total)

    accepted = 0
    rejected = 0
    skipped = 0

    for i, proposal in enumerate(proposals, 1):
        source = proposal["source_entity"]
        target = proposal["target_entity"]
        score = proposal["score"]
        src_ctx = proposal["source_context"]
        tgt_ctx = proposal["target_context"]

        src_types = ", ".join(src_ctx["source_types"]) if src_ctx["source_types"] else "none"
        tgt_types = ", ".join(tgt_ctx["source_types"]) if tgt_ctx["source_types"] else "none"

        print("--- Proposal %d/%d (score: %.0f) ---" % (i, total, score))
        print("  A: %s (%s)" % (source.name, source.entity_type))
        print("     Mentions: %d from %s" % (src_ctx["mention_count"], src_types))
        print("  B: %s (%s)" % (target.name, target.entity_type))
        print("     Mentions: %d from %s" % (tgt_ctx["mention_count"], tgt_types))
        print("  Canonical if merged: %s" % target.name)

        while True:
            try:
                choice = input("[a]ccept / [r]eject / [s]kip / [q]uit: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                choice = "q"

            if choice in ("a", "accept"):
                execute_merge(repo, source.id, target.id, score=score)
                accepted += 1
                print("  -> Merged '%s' into '%s'\n" % (source.name, target.name))
                break
            elif choice in ("r", "reject"):
                repo.save_proposal(
                    source.id, target.id,
                    reason="rejected by user",
                    status="rejected",
                )
                rejected += 1
                print("  -> Rejected\n")
                break
            elif choice in ("s", "skip"):
                skipped += 1
                print("  -> Skipped\n")
                break
            elif choice in ("q", "quit"):
                break
            else:
                print("  Invalid choice. Use a/r/s/q.")

        if choice in ("q", "quit"):
            break

    print("Review complete: %d merged, %d rejected, %d skipped" % (accepted, rejected, skipped))


def _cmd_split(repo: EntityRepository, args: argparse.Namespace) -> None:
    from src.entity.merger import execute_split

    # Need to find entity including deleted ones
    entity = repo.get_by_name_including_deleted(args.name)
    if entity is None:
        print("Entity not found: %s" % args.name, file=sys.stderr)
        sys.exit(1)

    if entity.deleted_at is None:
        print("Entity '%s' is not merged. Nothing to split." % entity.name)
        return

    try:
        execute_split(repo, entity.id)
        print("Split complete: '%s' restored as independent entity" % entity.name)
    except ValueError as e:
        print("Error: %s" % e, file=sys.stderr)
        sys.exit(1)


def _cmd_backfill(config, args: argparse.Namespace) -> None:
    from src.entity.backfill import run_backfill

    result = run_backfill(
        from_date=args.from_date,
        to_date=args.to_date,
        config=config,
        force=args.force,
    )
    print(
        "Summary: %d processed, %d skipped, %d entities registered"
        % (result["days_processed"], result["days_skipped"], result["entities_registered"])
    )
