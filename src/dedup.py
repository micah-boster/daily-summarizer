"""Algorithmic cross-source dedup pre-filter.

Consolidates near-identical items across sources before LLM synthesis.
Uses title similarity within the same calendar day as the matching signal.
Conservative threshold to minimize false positives.
"""
from __future__ import annotations

import logging
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

from src.config import PipelineConfig
from src.models.sources import SourceItem

logger = logging.getLogger(__name__)


def _titles_similar(title_a: str, title_b: str, threshold: float) -> float:
    """Compute similarity ratio between two titles.

    Args:
        title_a: First title.
        title_b: Second title.
        threshold: Minimum ratio to consider a match.

    Returns:
        Similarity ratio (0.0 to 1.0).
    """
    return SequenceMatcher(
        None, title_a.lower().strip(), title_b.lower().strip()
    ).ratio()


def _merge_items(items: list[SourceItem]) -> SourceItem:
    """Merge a cluster of duplicate items into one.

    Keeps the item with the longest content as the base, combines
    display_context and participants from all items.

    Args:
        items: List of duplicate SourceItems (at least 2).

    Returns:
        Single merged SourceItem.
    """
    # Pick item with longest content as base
    base = max(items, key=lambda i: len(i.content))

    # Combine display contexts
    all_contexts = []
    for item in items:
        ctx = item.display_context or item.source_type.value
        if ctx not in all_contexts:
            all_contexts.append(ctx)
    combined_context = ", ".join(all_contexts)

    # Union participants
    all_participants: set[str] = set()
    for item in items:
        all_participants.update(item.participants)

    # Earliest timestamp
    earliest = min(item.timestamp for item in items)

    # Build merged item
    return SourceItem(
        id=base.id,
        source_type=base.source_type,
        content_type=base.content_type,
        title=base.title,
        timestamp=earliest,
        content=base.content,
        summary=base.summary,
        participants=sorted(all_participants),
        source_url=base.source_url,
        display_context=combined_context,
        context={
            **base.context,
            "dedup_sources": [
                {"id": item.id, "source_type": item.source_type.value}
                for item in items
            ],
        },
        raw_data=base.raw_data,
    )


def _log_merge_decision(
    log_dir: Path,
    target_date: date,
    items: list[SourceItem],
    ratio: float,
) -> None:
    """Write a merge decision to the dedup log file.

    Args:
        log_dir: Directory for dedup log files.
        target_date: Date being processed.
        items: Items that were merged.
        ratio: Similarity score that triggered the merge.
    """
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    log_path = log_dir_path / f"dedup_{target_date.isoformat()}.log"

    titles = [f"'{item.title}' ({item.display_context or item.source_type.value})" for item in items]
    line = f"Merged {' + '.join(titles)} -- score: {ratio:.2f}\n"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def dedup_source_items(
    items: list[SourceItem],
    config: PipelineConfig,
    target_date: date,
) -> list[SourceItem]:
    """Deduplicate source items using title similarity within the same day.

    Groups items by calendar day, compares titles pairwise, and merges
    near-identical items. Logs all merge decisions to a separate file.

    Args:
        items: All source items from ingest.
        config: Pipeline config with dedup settings.
        target_date: The pipeline target date.

    Returns:
        Deduplicated list of SourceItems.
    """
    if not config.dedup.enabled:
        return items

    if not items:
        return []

    threshold = config.dedup.similarity_threshold
    log_dir = config.dedup.log_dir

    # Group items by calendar day — only process target_date items
    target_items: list[SourceItem] = []
    other_items: list[SourceItem] = []
    for item in items:
        if item.timestamp.date() == target_date:
            target_items.append(item)
        else:
            other_items.append(item)

    if len(target_items) <= 1:
        return items

    # Build clusters using greedy matching
    n = len(target_items)
    merged_into: list[int] = list(range(n))  # Union-find parent

    def find(i: int) -> int:
        while merged_into[i] != i:
            merged_into[i] = merged_into[merged_into[i]]
            i = merged_into[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            ratio = _titles_similar(target_items[i].title, target_items[j].title, threshold)
            if ratio >= threshold:
                ri, rj = find(i), find(j)
                if ri != rj:
                    merged_into[rj] = ri

    # Group items by cluster root
    clusters: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        clusters.setdefault(root, []).append(i)

    # Build result
    result: list[SourceItem] = list(other_items)
    for root, indices in clusters.items():
        cluster_items = [target_items[i] for i in indices]
        if len(cluster_items) == 1:
            result.append(cluster_items[0])
        else:
            # Compute the pairwise max ratio for logging
            max_ratio = 0.0
            for i in range(len(cluster_items)):
                for j in range(i + 1, len(cluster_items)):
                    r = _titles_similar(
                        cluster_items[i].title, cluster_items[j].title, threshold
                    )
                    max_ratio = max(max_ratio, r)

            merged = _merge_items(cluster_items)
            result.append(merged)
            _log_merge_decision(log_dir, target_date, cluster_items, max_ratio)

    return result
