"""Stage 2: Daily cross-meeting synthesis via Claude API.

Merges per-meeting extractions into a unified daily intelligence brief
organized by the three core questions: Substance, Decisions, Commitments.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import anthropic

from src.config import PipelineConfig
from src.models.sources import SourceItem, SourceType
from src.synthesis.models import MeetingExtraction
from src.retry import retry_api_call
from src.synthesis.validator import validate_evidence_only

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_OUTPUT_TOKENS = 8192

# Token budget constants
TOKEN_BUDGET = 100_000
CHARS_PER_TOKEN = 4
CHAR_BUDGET = TOKEN_BUDGET * CHARS_PER_TOKEN  # 400,000 chars
SAFETY_MARGIN = 0.8  # Use 80% of budget for safety
EFFECTIVE_CHAR_BUDGET = int(CHAR_BUDGET * SAFETY_MARGIN)  # 320,000 chars


@retry_api_call
def _call_claude_with_retry(client, model, max_tokens, prompt):
    """Call Claude API with retry on transient errors."""
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )

EXECUTIVE_SUMMARY_INSTRUCTION = """## Executive Summary
[Provide 3-5 sentences summarizing the most significant items from today's meetings. Focus on decisions with broad impact, new commitments with tight deadlines, and substance that changes direction.]

"""

SYNTHESIS_PROMPT = """You are producing a daily intelligence brief. Be concise. Every word must earn its place.

Date: {date}
Number of meetings with transcripts: {transcript_count}
Number of Slack sources: {slack_source_count}
Number of Google Docs sources: {docs_source_count}
Number of HubSpot sources: {hubspot_source_count}

{extractions_text}

{slack_items_text}

{docs_items_text}

{hubspot_items_text}

{priority_context}

CROSS-SOURCE DEDUPLICATION:
- When the SAME specific topic appears across multiple sources, consolidate into ONE item.
- "Same topic" = same project + same specific issue/decision/action. NOT just same project name.
- Append all source attributions: "Timeline moved to Q3 (per standup, per Slack #proj-alpha)"
- CONFLICTING details: show both with attribution: "Launch March 15 (per standup) vs March 22 (per Slack #releases)"
- UNCERTAIN matches: keep SEPARATE. Two items > one incorrectly merged item.
- Never merge items from different projects, even if they discuss similar themes.

Produce a daily summary with these exact sections:

{executive_summary_instruction}## Substance
One bullet per distinct thing that happened. Keep it concise but include enough context to be useful standalone.
- [What happened] — [Source meeting, Slack, Google Doc, or HubSpot attribution]

## Decisions
One bullet per decision. Merge duplicates across meetings. Always include who decided.
- [What was decided] — [Who decided] — [Source meeting, Slack, Google Doc, or HubSpot attribution]

## Commitments
One row per commitment. Extract ONLY explicit commitments (someone clearly said they will do something).
Include everyone's commitments, not just the user's.
Do NOT extract suggestions ("We should probably...") or observations ("The report needs updating").
Only extract "I will..." / "X will..." / "X agreed to..." statements.

| Who | What | By When | Source |
|-----|------|---------|--------|
| [First name or "TBD"] | [What they committed to] | [Normalized date relative to {date}, or "unspecified"] | [Source attribution(s)] |

Date normalization: "by Friday" = next Friday's date. "next week" = "week of YYYY-MM-DD". "end of day" = "{date}". "soon" or no deadline = "unspecified".

CRITICAL RULES:
- CONCISE: Each bullet should be 1-2 short sentences max. No filler words.
- CONTEXT: Every bullet must be understandable on its own without reading the full document. Include enough specifics.
- OWNERS: Every commitment MUST name who owns it. Never write a commitment without an owner.
- DEDUPLICATE: If the same topic came up in multiple meetings, write ONE bullet and list both meetings.
- DEDUP COMMITMENTS: Same commitment in meeting AND Slack = one row with both sources.
- COMMITMENTS TABLE: Every row must have a Who. Use "TBD" if unclear.
- Slack items use their attribution format exactly as provided (e.g., "(per Slack #design-team)" or "(per Slack DM with Sarah Chen)").
- Google Docs items use their attribution format exactly as provided (e.g., "(per Google Doc Project Roadmap)").
- HubSpot items use their attribution format exactly as provided (e.g., "(per HubSpot deal Acme Renewal)" or "(per HubSpot contact John Smith)").
- Merge duplicate topics across meetings, Slack, Google Docs, AND HubSpot. One bullet, multiple sources.
- NO PADDING: "Hire HubSpot vendor (<$5K)" not "Team decided to move forward with hiring an external vendor for HubSpot onboarding and professional flow building."
- Source meeting, Slack, Google Doc, or HubSpot attribution goes at end after an em dash.
- Neutral tone. Facts only.
- If a category has no items, write "No items for this day."
"""


def _estimate_and_truncate(
    extractions_text: str,
    slack_items_text: str,
    docs_items_text: str,
    hubspot_items_text: str,
    base_prompt_chars: int = 3000,
) -> tuple[str, str, str, str, list[str]]:
    """Estimate token usage and truncate low-priority sources if over budget.

    Sources are truncated in priority order (lowest first):
    1. Google Docs (lowest priority)
    2. HubSpot
    3. Slack
    4. Meeting transcripts (NEVER truncated — highest priority)

    Args:
        extractions_text: Formatted meeting extractions text.
        slack_items_text: Formatted Slack items text.
        docs_items_text: Formatted Google Docs items text.
        hubspot_items_text: Formatted HubSpot items text.
        base_prompt_chars: Estimated character count for the base prompt template.

    Returns:
        Tuple of (extractions_text, slack_text, docs_text, hubspot_text, truncated_sources).
        truncated_sources is a list of source names that were removed.
    """
    total = (
        len(extractions_text)
        + len(slack_items_text)
        + len(docs_items_text)
        + len(hubspot_items_text)
        + base_prompt_chars
    )

    if total <= EFFECTIVE_CHAR_BUDGET:
        return extractions_text, slack_items_text, docs_items_text, hubspot_items_text, []

    truncated: list[str] = []

    # Truncate in priority order: Docs -> HubSpot -> Slack -> (never transcripts)
    if total > EFFECTIVE_CHAR_BUDGET and docs_items_text:
        total -= len(docs_items_text)
        docs_items_text = ""
        truncated.append("Google Docs")
        logger.warning("Token budget: truncated Google Docs items (%d chars over budget)", total - EFFECTIVE_CHAR_BUDGET if total > EFFECTIVE_CHAR_BUDGET else 0)

    if total > EFFECTIVE_CHAR_BUDGET and hubspot_items_text:
        total -= len(hubspot_items_text)
        hubspot_items_text = ""
        truncated.append("HubSpot")
        logger.warning("Token budget: truncated HubSpot items")

    if total > EFFECTIVE_CHAR_BUDGET and slack_items_text:
        total -= len(slack_items_text)
        slack_items_text = ""
        truncated.append("Slack")
        logger.warning("Token budget: truncated Slack items")

    if truncated:
        logger.warning(
            "Token budget enforcement: truncated %s (estimated %d chars / %d budget)",
            ", ".join(truncated),
            total + sum(len(s) for s in [docs_items_text, hubspot_items_text, slack_items_text]),
            EFFECTIVE_CHAR_BUDGET,
        )

    return extractions_text, slack_items_text, docs_items_text, hubspot_items_text, truncated


def _format_extractions_for_prompt(extractions: list[MeetingExtraction]) -> str:
    """Format meeting extractions into readable text for the synthesis prompt.

    Each meeting gets a header with title/time/participants, then its
    non-empty categories listed. Low-signal extractions are skipped.

    Args:
        extractions: List of MeetingExtraction objects from Stage 1.

    Returns:
        Formatted text block for inclusion in the synthesis prompt.
    """
    blocks: list[str] = []

    for ext in extractions:
        if ext.low_signal:
            continue

        lines: list[str] = [
            f"### {ext.meeting_title} ({ext.meeting_time})",
            f"Participants: {', '.join(ext.meeting_participants) if ext.meeting_participants else 'Not listed'}",
            "",
        ]

        categories = [
            ("Decisions", ext.decisions),
            ("Commitments", ext.commitments),
            ("Substance", ext.substance),
            ("Open Questions", ext.open_questions),
            ("Tensions", ext.tensions),
        ]

        for cat_name, items in categories:
            if not items:
                continue
            lines.append(f"**{cat_name}:**")
            for item in items:
                parts = [f"- {item.content}"]
                if item.participants:
                    parts.append(f"  (Participants: {', '.join(item.participants)})")
                if item.rationale:
                    parts.append(f"  Rationale: {item.rationale}")
                lines.append("\n".join(parts))
            lines.append("")

        blocks.append("\n".join(lines))

    return "\n---\n\n".join(blocks)


def _format_slack_items_for_prompt(slack_items: list[SourceItem]) -> str:
    """Format Slack SourceItems into readable text for the synthesis prompt.

    Groups items by display_context (channel/DM name). Each group gets a
    header, then items listed with sender name, content, and timestamp.

    Args:
        slack_items: List of SourceItem objects from Slack ingestion.

    Returns:
        Formatted text block for inclusion in the synthesis prompt.
    """
    if not slack_items:
        return ""

    # Group by display_context
    groups: dict[str, list[SourceItem]] = {}
    for item in slack_items:
        key = item.display_context or "Slack"
        groups.setdefault(key, []).append(item)

    blocks: list[str] = ["## Slack Activity\n"]

    for context, items in groups.items():
        blocks.append(f"### {context}")
        for item in items:
            if item.source_type == SourceType.SLACK_THREAD:
                # Thread: show full content block
                blocks.append(f"**Thread:** {item.title}")
                blocks.append(item.content)
                blocks.append(f"  {item.attribution_text()}")
            else:
                # Individual message
                ts_str = item.timestamp.strftime("%H:%M")
                blocks.append(f"- {item.title}: {item.content} ({ts_str}) {item.attribution_text()}")
        blocks.append("")

    return "\n".join(blocks)


def _format_docs_items_for_prompt(docs_items: list[SourceItem]) -> str:
    """Format Google Docs SourceItems into readable text for the synthesis prompt.

    Groups items by display_context (doc name). Each group gets a
    header, then items listed with content and attribution.

    Args:
        docs_items: List of SourceItem objects from Google Docs ingestion.

    Returns:
        Formatted text block for inclusion in the synthesis prompt.
    """
    if not docs_items:
        return ""

    # Group by display_context
    groups: dict[str, list[SourceItem]] = {}
    for item in docs_items:
        key = item.display_context or "Google Doc"
        groups.setdefault(key, []).append(item)

    blocks: list[str] = ["## Google Docs Activity\n"]

    for context, items in groups.items():
        blocks.append(f"### {context}")
        for item in items:
            if item.source_type == SourceType.GOOGLE_DOC_EDIT:
                blocks.append(f"**Edited:** {item.title}")
                if item.content and not item.content.startswith("["):
                    # Show first 200 chars of content in prompt
                    preview = item.content[:200]
                    if len(item.content) > 200:
                        preview += "..."
                    blocks.append(f"  Content: {preview}")
                else:
                    blocks.append(f"  {item.content}")
                blocks.append(f"  {item.attribution_text()}")
            elif item.source_type == SourceType.GOOGLE_DOC_COMMENT:
                ts_str = item.timestamp.strftime("%H:%M")
                blocks.append(f"- {item.title}: {item.content} ({ts_str}) {item.attribution_text()}")
        blocks.append("")

    return "\n".join(blocks)


def _format_hubspot_items_for_prompt(hubspot_items: list[SourceItem]) -> str:
    """Format HubSpot SourceItems into readable text for the synthesis prompt.

    Groups items by source_type (deals, contacts, tickets, activities).

    Args:
        hubspot_items: List of SourceItem objects from HubSpot ingestion.

    Returns:
        Formatted text block for inclusion in the synthesis prompt.
    """
    if not hubspot_items:
        return ""

    # Group by source_type
    deals = [i for i in hubspot_items if i.source_type == SourceType.HUBSPOT_DEAL]
    contacts = [i for i in hubspot_items if i.source_type == SourceType.HUBSPOT_CONTACT]
    tickets = [i for i in hubspot_items if i.source_type == SourceType.HUBSPOT_TICKET]
    activities = [i for i in hubspot_items if i.source_type == SourceType.HUBSPOT_ACTIVITY]

    blocks: list[str] = ["## HubSpot CRM Activity\n"]

    if deals:
        blocks.append(f"### Deals ({len(deals)})")
        for item in deals:
            blocks.append(f"- **{item.title}**: {item.content} {item.attribution_text()}")
        blocks.append("")

    if contacts:
        blocks.append(f"### Contacts ({len(contacts)})")
        for item in contacts:
            blocks.append(f"- **{item.title}**: {item.content} {item.attribution_text()}")
        blocks.append("")

    if tickets:
        blocks.append(f"### Tickets ({len(tickets)})")
        for item in tickets:
            blocks.append(f"- **{item.title}**: {item.content} {item.attribution_text()}")
        blocks.append("")

    if activities:
        blocks.append(f"### Activities ({len(activities)})")
        for item in activities:
            blocks.append(f"- **{item.title}**: {item.content} {item.attribution_text()}")
        blocks.append("")

    return "\n".join(blocks)


def _dedup_hubspot_items(
    hubspot_items: list[SourceItem],
    extractions: list,
    slack_items: list[SourceItem] | None = None,
) -> list[SourceItem]:
    """Remove HubSpot items that duplicate content from other sources.

    - HubSpot meetings: skip if a calendar event with matching start time exists
    - HubSpot emails: skip if a matching email subject/timestamp exists in other sources

    Args:
        hubspot_items: Items from HubSpot ingestion.
        extractions: Meeting extractions from calendar/transcript pipeline.
        slack_items: Optional Slack items for comparison.

    Returns:
        Filtered list of HubSpot items with duplicates removed.
    """
    if not hubspot_items:
        return []

    # Collect calendar event times for dedup (within 5 min window)
    calendar_times: set[int] = set()
    for ext in extractions:
        if hasattr(ext, "meeting_start") and ext.meeting_start:
            try:
                ts = ext.meeting_start
                if hasattr(ts, "timestamp"):
                    # Round to 5-min buckets for fuzzy matching
                    calendar_times.add(int(ts.timestamp()) // 300)
            except Exception:
                pass

    filtered: list[SourceItem] = []
    for item in hubspot_items:
        # Skip HubSpot meetings that match calendar events
        if item.source_type == SourceType.HUBSPOT_ACTIVITY and "meeting" in item.id:
            item_bucket = int(item.timestamp.timestamp()) // 300
            if item_bucket in calendar_times:
                logger.debug("Dedup: skipping HubSpot meeting %s (matches calendar event)", item.id)
                continue

        # Skip HubSpot emails that match calendar/gmail emails by timestamp bucket
        if item.source_type == SourceType.HUBSPOT_ACTIVITY and "email" in item.id:
            item_bucket = int(item.timestamp.timestamp()) // 120  # 2-min window
            # For now, keep emails unless we have explicit gmail item comparison
            # (Gmail items are in extractions, not separate SourceItems currently)

        filtered.append(item)

    if len(filtered) < len(hubspot_items):
        logger.info(
            "HubSpot dedup: removed %d duplicate items",
            len(hubspot_items) - len(filtered),
        )

    return filtered


def _parse_synthesis_response(response_text: str) -> dict:
    """Parse Claude's synthesis response into structured sections.

    Args:
        response_text: Claude's full response text.

    Returns:
        Dict with keys: executive_summary (str or None), substance (list[str]),
        decisions (list[str]), commitments (list[str]).
    """
    result: dict = {
        "executive_summary": None,
        "substance": [],
        "decisions": [],
        "commitments": [],
    }

    # Split by ## headers
    sections: dict[str, str] = {}
    current_section = ""
    current_content: list[str] = []

    for line in response_text.split("\n"):
        if line.startswith("## "):
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = line[3:].strip().lower()
            current_content = []
        else:
            current_content.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    # Extract executive summary
    if "executive summary" in sections:
        summary = sections["executive summary"].strip()
        if summary and summary.lower() != "no items for this day.":
            result["executive_summary"] = summary

    # Extract items from each section as formatted strings
    for section_key, result_key in [
        ("substance", "substance"),
        ("decisions", "decisions"),
        ("commitments", "commitments"),
    ]:
        section_text = sections.get(section_key, "")
        if not section_text or section_text.strip().lower() in (
            "no items for this day.",
            "no items for this day",
        ):
            continue

        items: list[str] = []

        if section_key == "commitments":
            # Parse commitments as table rows (pipe-delimited) or bullet items
            for line in section_text.split("\n"):
                stripped = line.strip()
                # Skip table header and separator rows
                if stripped.startswith("| Who") or stripped.startswith("|--"):
                    continue
                # Parse pipe-delimited table rows
                if stripped.startswith("|") and stripped.endswith("|"):
                    item = stripped.strip()
                    if item:
                        items.append(item)
                # Fallback: also accept bullet-list format for backward compatibility
                elif stripped.startswith("- "):
                    item = stripped[2:].strip()
                    if item:
                        items.append(item)
        else:
            # Extract bullet items (lines starting with -)
            for line in section_text.split("\n"):
                stripped = line.strip()
                if stripped.startswith("- "):
                    item = stripped[2:].strip()
                    if item:
                        items.append(item)

        result[result_key] = items

    return result


def synthesize_daily(
    extractions: list[MeetingExtraction],
    target_date: date,
    config: PipelineConfig,
    slack_items: list[SourceItem] | None = None,
    docs_items: list[SourceItem] | None = None,
    hubspot_items: list[SourceItem] | None = None,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """Produce daily synthesis from meeting extractions, Slack, Docs, and HubSpot items.

    Stage 2 of the two-stage pipeline. Takes all per-meeting extractions
    and optional Slack/Docs/HubSpot SourceItems, builds the synthesis prompt,
    calls Claude, parses the response, and validates for evidence-only language.

    Args:
        extractions: List of MeetingExtraction from Stage 1.
        target_date: The date being synthesized.
        config: Pipeline configuration dict.
        slack_items: Optional list of SourceItem from Slack ingestion.
        docs_items: Optional list of SourceItem from Google Docs ingestion.
        hubspot_items: Optional list of SourceItem from HubSpot ingestion.

    Returns:
        Dict with keys: substance (list[str]), decisions (list[str]),
        commitments (list[str]), executive_summary (str or None).
    """
    empty_result: dict = {
        "substance": [],
        "decisions": [],
        "commitments": [],
        "executive_summary": None,
    }

    # Filter out low-signal extractions
    substantive = [e for e in extractions if not e.low_signal]
    has_slack = bool(slack_items)
    has_docs = bool(docs_items)
    has_hubspot = bool(hubspot_items)

    if not substantive and not has_slack and not has_docs and not has_hubspot:
        logger.info("No substantive extractions, Slack, Docs, or HubSpot items for %s, returning empty synthesis", target_date)
        return empty_result

    # Cross-source dedup for HubSpot items
    deduped_hubspot = _dedup_hubspot_items(hubspot_items or [], substantive, slack_items)

    # Build prompt components
    extractions_text = _format_extractions_for_prompt(substantive)
    slack_items_text = _format_slack_items_for_prompt(slack_items or [])
    docs_items_text = _format_docs_items_for_prompt(docs_items or [])
    hubspot_items_text = _format_hubspot_items_for_prompt(deduped_hubspot)

    # Token budget enforcement: truncate if over budget
    extractions_text, slack_items_text, docs_items_text, hubspot_items_text, truncated_sources = (
        _estimate_and_truncate(extractions_text, slack_items_text, docs_items_text, hubspot_items_text)
    )

    transcript_count = len(substantive)
    slack_source_count = len(slack_items) if slack_items else 0
    docs_source_count = len(docs_items) if docs_items else 0
    hubspot_source_count = len(deduped_hubspot)

    # Conditional executive summary for busy days (5+ meetings with transcripts)
    exec_instruction = ""
    if transcript_count >= 5:
        exec_instruction = EXECUTIVE_SUMMARY_INSTRUCTION

    # Build priority context for prompt injection
    priority_context = ""
    try:
        from src.priorities import build_priority_context, load_priorities

        priorities = load_priorities()
        priority_context = build_priority_context(priorities, substantive)
        if priority_context:
            logger.info("Priority context injected into synthesis prompt")
    except Exception as e:
        logger.warning("Priority loading failed: %s. Continuing without priorities.", e)

    prompt = SYNTHESIS_PROMPT.format(
        date=target_date.isoformat(),
        transcript_count=transcript_count,
        slack_source_count=slack_source_count,
        docs_source_count=docs_source_count,
        hubspot_source_count=hubspot_source_count,
        extractions_text=extractions_text,
        slack_items_text=slack_items_text,
        docs_items_text=docs_items_text,
        hubspot_items_text=hubspot_items_text,
        executive_summary_instruction=exec_instruction,
        priority_context=priority_context,
    )

    # Get model settings from config
    model = config.synthesis.model
    max_tokens = config.synthesis.synthesis_max_output_tokens

    # Call Claude API with retry
    client = client or anthropic.Anthropic()
    response = _call_claude_with_retry(client, model, max_tokens, prompt)
    response_text = response.content[0].text

    # Validate evidence-only language
    violations = validate_evidence_only(response_text)
    if violations:
        logger.warning(
            "Synthesis contains %d evaluative language violation(s) for %s:",
            len(violations),
            target_date,
        )
        for v in violations[:5]:  # Log first 5
            logger.warning("  [%s] '%s' in: ...%s...", v.pattern, v.text, v.context)

    # Parse response
    result = _parse_synthesis_response(response_text)

    # Track truncated sources for downstream consumers
    if truncated_sources:
        result["truncated_sources"] = truncated_sources

    logger.info(
        "Synthesis for %s: %d substance, %d decisions, %d commitments%s%s",
        target_date,
        len(result["substance"]),
        len(result["decisions"]),
        len(result["commitments"]),
        " (with executive summary)" if result["executive_summary"] else "",
        f" [truncated: {', '.join(truncated_sources)}]" if truncated_sources else "",
    )

    return result
