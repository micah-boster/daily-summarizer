"""Merge proposal list, approve, and reject endpoints."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.deps import get_entity_repo
from src.api.models.responses import EntityListItem, MergeProposalResponse
from src.entity.merger import execute_merge, generate_proposals
from src.entity.repository import EntityRepository

router = APIRouter(prefix="/merge-proposals", tags=["merge-proposals"])


class ApproveRequest(BaseModel):
    """Request body for approving a merge proposal."""

    primary_entity_id: str


@router.get("", response_model=list[MergeProposalResponse])
def list_merge_proposals(
    repo: EntityRepository = Depends(get_entity_repo),
) -> list[MergeProposalResponse]:
    """Return pending merge proposals with enriched entity details."""
    raw_proposals = generate_proposals(repo)
    results: list[MergeProposalResponse] = []

    for p in raw_proposals:
        source = p["source_entity"]
        target = p["target_entity"]
        source_stats = repo.get_entity_stats(source.id)
        target_stats = repo.get_entity_stats(target.id)

        results.append(
            MergeProposalResponse(
                proposal_id="",  # Fresh proposals don't have DB IDs yet
                source_entity=EntityListItem(
                    entity_id=source.id,
                    name=source.name,
                    entity_type=str(source.entity_type),
                    mention_count=source_stats["mention_count"],
                    commitment_count=source_stats["commitment_count"],
                    last_active_date=source_stats["last_active_date"],
                ),
                target_entity=EntityListItem(
                    entity_id=target.id,
                    name=target.name,
                    entity_type=str(target.entity_type),
                    mention_count=target_stats["mention_count"],
                    commitment_count=target_stats["commitment_count"],
                    last_active_date=target_stats["last_active_date"],
                ),
                score=p["score"],
                reason=None,
                status="pending",
                created_at="",
            )
        )

    return results


@router.post("/{proposal_id}/approve", response_model=MergeProposalResponse)
def approve_merge_proposal(
    proposal_id: str,
    body: ApproveRequest,
    repo: EntityRepository = Depends(get_entity_repo),
) -> MergeProposalResponse:
    """Approve a merge proposal and execute the merge.

    The primary_entity_id indicates which entity to keep. The other entity
    gets merged into it (soft-deleted, mentions reassigned, aliases transferred).
    """
    # For fresh proposals (no DB ID), proposal_id encodes "source_id:target_id"
    # For DB proposals, look up by ID first
    source_id: str | None = None
    target_id: str | None = None

    if ":" in proposal_id:
        # Encoded pair format: source_id:target_id
        parts = proposal_id.split(":", 1)
        source_id, target_id = parts[0], parts[1]
    else:
        # Look up from DB
        row = repo._conn.execute(
            "SELECT * FROM merge_proposals WHERE id = ? AND status = 'pending'",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Proposal not found")
        source_id = row["source_entity_id"]
        target_id = row["target_entity_id"]
        # Update status
        repo.update_proposal_status(proposal_id, "approved")

    # Determine which is primary (to keep) and which is source (to merge away)
    primary_id = body.primary_entity_id
    if primary_id == target_id:
        merge_source_id = source_id
        merge_target_id = target_id
    elif primary_id == source_id:
        merge_source_id = target_id
        merge_target_id = source_id
    else:
        raise HTTPException(
            status_code=400,
            detail="primary_entity_id must be one of the two entities in the proposal",
        )

    try:
        execute_merge(repo, merge_source_id, merge_target_id)
    except sqlite3.OperationalError:
        raise HTTPException(status_code=503, detail="Database busy")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Return the result
    kept = repo.get_by_id(merge_target_id)
    merged = repo._conn.execute(
        "SELECT * FROM entities WHERE id = ?", (merge_source_id,)
    ).fetchone()

    kept_stats = repo.get_entity_stats(merge_target_id)

    return MergeProposalResponse(
        proposal_id=proposal_id,
        source_entity=EntityListItem(
            entity_id=merged["id"] if merged else merge_source_id,
            name=merged["name"] if merged else "Unknown",
            entity_type=merged["entity_type"] if merged else "",
            mention_count=0,
            commitment_count=0,
            last_active_date=None,
        ),
        target_entity=EntityListItem(
            entity_id=kept.id if kept else merge_target_id,
            name=kept.name if kept else "Unknown",
            entity_type=str(kept.entity_type) if kept else "",
            mention_count=kept_stats["mention_count"],
            commitment_count=kept_stats["commitment_count"],
            last_active_date=kept_stats["last_active_date"],
        ),
        score=0.0,
        reason=None,
        status="approved",
        created_at="",
    )


@router.post("/{proposal_id}/reject", response_model=MergeProposalResponse)
def reject_merge_proposal(
    proposal_id: str,
    repo: EntityRepository = Depends(get_entity_repo),
) -> MergeProposalResponse:
    """Reject a merge proposal (status update only, no entity changes)."""
    source_id: str | None = None
    target_id: str | None = None

    if ":" in proposal_id:
        # Encoded pair: save as rejected proposal to prevent re-proposing
        parts = proposal_id.split(":", 1)
        source_id, target_id = parts[0], parts[1]
        try:
            repo.save_proposal(source_id, target_id, reason="rejected by user", status="rejected")
        except sqlite3.OperationalError:
            raise HTTPException(status_code=503, detail="Database busy")
    else:
        row = repo._conn.execute(
            "SELECT * FROM merge_proposals WHERE id = ?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Proposal not found")
        source_id = row["source_entity_id"]
        target_id = row["target_entity_id"]
        try:
            repo.update_proposal_status(proposal_id, "rejected")
        except sqlite3.OperationalError:
            raise HTTPException(status_code=503, detail="Database busy")

    source = repo.get_by_id(source_id)
    target = repo.get_by_id(target_id)
    source_stats = repo.get_entity_stats(source_id) if source else {"mention_count": 0, "commitment_count": 0, "last_active_date": None}
    target_stats = repo.get_entity_stats(target_id) if target else {"mention_count": 0, "commitment_count": 0, "last_active_date": None}

    return MergeProposalResponse(
        proposal_id=proposal_id,
        source_entity=EntityListItem(
            entity_id=source_id,
            name=source.name if source else "Unknown",
            entity_type=str(source.entity_type) if source else "",
            mention_count=source_stats["mention_count"],
            commitment_count=source_stats["commitment_count"],
            last_active_date=source_stats["last_active_date"],
        ),
        target_entity=EntityListItem(
            entity_id=target_id,
            name=target.name if target else "Unknown",
            entity_type=str(target.entity_type) if target else "",
            mention_count=target_stats["mention_count"],
            commitment_count=target_stats["commitment_count"],
            last_active_date=target_stats["last_active_date"],
        ),
        score=0.0,
        reason="rejected by user",
        status="rejected",
        created_at="",
    )
