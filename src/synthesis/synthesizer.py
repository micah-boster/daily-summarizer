"""Stage 2: Daily cross-meeting synthesis via Claude API using structured outputs.

Merges per-meeting extractions into a unified daily intelligence brief
organized by the three core questions: Substance, Decisions, Commitments.
Uses json_schema constrained decoding for guaranteed valid output.
"""

from __future__ import annotations

import json
import logging
from datetime import date

import anthropic

from src.config import PipelineConfig
from src.models.sources import SourceItem, SourceType
from src.synthesis.models import CommitmentRow, DailySynthesisOutput, MeetingExtraction, SynthesisItem
from src.retry import retry_api_call
from src.schema_utils import prepare_schema_for_claude
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
def _call_claude_structured_with_retry(client, model, max_tokens, prompt, schema):
    """Call Claude structured outputs API with retry on transient errors."""
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        tools=[{"name": "output", "description": "Structured output", "input_schema": schema}],
        tool_choice={"type": "tool", "name": "output"},
    )


EXECUTIVE_SUMMARY_INSTRUCTION = """Note: Since there are 5+ meetings with transcripts, provide an executive_summary (3-5 sentences summarizing the most significant items, focusing on decisions with broad impact, new commitments with tight deadlines, and substance that changes direction).

"""

SYNTHESIS_PROMPT = """You are producing a daily intelligence brief as structured JSON. Be concise. Every word must earn its place.

Date: {date}
Number of meetings with transcripts: {transcript_count}
Number of Slack sources: {slack_source_count}
Number of Google Docs sources: {docs_source_count}
Number of HubSpot sources: {hubspot_source_count}
Number of Notion sources: {notion_source_count}

{extractions_text}

{slack_items_text}

{docs_items_text}

{hubspot_items_text}

{notion_items_text}

{priority_context}

CROSS-SOURCE DEDUPLICATION:
- When the SAME specific topic appears across multiple sources, consolidate into ONE item.
- "Same topic" = same project + same specific issue/decision/action. NOT just same project name.
- Append all source attributions: "Timeline moved to Q3 (per standup, per Slack #proj-alpha)"
- CONFLICTING details: show both with attribution: "Launch March 15 (per standup) vs March 22 (per Slack #releases)"
- UNCERTAIN matches: keep SEPARATE. Two items > one incorrectly merged item.
- Never merge items from different projects, even if they discuss similar themes.

Use the reasoning field for your cross-source deduplication analysis before structuring the output.

{executive_summary_instruction}FIELD GUIDANCE:

substance items: Each content field should be a concise sentence about what happened, with source attribution at the end after an em dash. Example: "Q2 pipeline has 3 deals over $100k — Team Sync"

decisions items: Each content field should include what was decided, who decided, and source attribution. Example: "Delay product launch to Q3 — Sarah, Mike — Team Sync"

commitments: Extract ONLY explicit commitments (someone clearly said they will do something). Include everyone's, not just the user's. Do NOT extract suggestions or observations.
- who: First name of the person who committed, or "TBD" if unclear
- what: Concise description of what they committed to
- by_when: Normalized date relative to {date}. "by Friday" = next Friday's ISO date. "next week" = "week of YYYY-MM-DD". "end of day" = "{date}". "soon" or no deadline = "unspecified"
- source: Attribution text (e.g., "Team Sync", "Slack #proj-alpha", "HubSpot deal Acme Renewal")

executive_summary: Provide 3-5 sentences summarizing the most significant items ONLY if there are 5+ meetings with transcripts. Otherwise set to null.

ENTITY EXTRACTION:
For each substance item, decision, and commitment, include an "entity_names" list containing the names of any companies, organizations, or individual people mentioned in that item. Use full formal names (e.g., "Affirm Inc", "Colin Roberts"). If no entities are mentioned, leave the list empty.

CRITICAL RULES:
- CONCISE: Each item should be 1-2 short sentences max. No filler words.
- CONTEXT: Every item must be understandable on its own. Include enough specifics.
- OWNERS: Every commitment MUST name who owns it.
- DEDUPLICATE: Same topic in multiple sources = ONE item with all sources listed.
- NO PADDING: "Hire HubSpot vendor (<$5K)" not verbose alternatives.
- Slack items use their attribution format exactly as provided.
- Google Docs items use their attribution format exactly as provided.
- HubSpot items use their attribution format exactly as provided.
- Notion items use their attribution format exactly as provided.
- Neutral tone. Facts only.
- If a category has no items, leave the list empty.
"""


def _estimate_and_truncate(
    extractions_text: str,
    slack_items_text: str,
    docs_items_text: str,
    hubspot_items_text: str,
    notion_items_text: str = "",
    base_prompt_chars: int = 3000,
) -> tuple[str, str, str, str, str, list[str]]:
    """Estimate token usage and truncate low-priority sources if over budget.

    Sources are truncated in priority order (lowest first):
    1. Notion (lowest priority — newest source)
    2. Google Docs
    3. HubSpot
    4. Slack
    5. Meeting transcripts (NEVER truncated — highest priority)

    Args:
        extractions_text: Formatted meeting extractions text.
        slack_items_text: Formatted Slack items text.
        docs_items_text: Formatted Google Docs items text.
        hubspot_items_text: Formatted HubSpot items text.
        notion_items_text: Formatted Notion items text.
        base_prompt_chars: Estimated character count for the base prompt template.

    Returns:
        Tuple of (extractions_text, slack_text, docs_text, hubspot_text, notion_text, truncated_sources).
        truncated_sources is a list of source names that were removed.
    """
    total = (
        len(extractions_text)
        + len(slack_items_text)
        + len(docs_items_text)
        + len(hubspot_items_text)
        + len(notion_items_text)
        + base_prompt_chars
    )

    if total <= EFFECTIVE_CHAR_BUDGET:
        return extractions_text, slack_items_text, docs_items_text, hubspot_items_text, notion_items_text, []

    truncated: list[str] = []

    # Truncate in priority order: Notion -> Docs -> HubSpot -> Slack -> (never transcripts)
    if total > EFFECTIVE_CHAR_BUDGET and notion_items_text:
        total -= len(notion_items_text)
        notion_items_text = ""
        truncated.append("Notion")
        logger.warning("Token budget: truncated Notion items")

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
            total + sum(len(s) for s in [docs_items_text, hubspot_items_text, slack_items_text, notion_items_text]),
            EFFECTIVE_CHAR_BUDGET,
        )

    return extractions_text, slack_items_text, docs_items_text, hubspot_items_text, notion_items_text, truncated


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


def _convert_synthesis_to_dict(output: DailySynthesisOutput) -> dict:
    """Convert DailySynthesisOutput to dict preserving full objects.

    Returns full SynthesisItem and CommitmentRow objects so downstream
    consumers can access entity_names for attribution. Consumers that
    need string content use .content on SynthesisItem or format
    CommitmentRow fields directly.

    Args:
        output: Validated DailySynthesisOutput from API response.

    Returns:
        Dict with keys: substance (list[SynthesisItem]),
        decisions (list[SynthesisItem]), commitments (list[CommitmentRow]),
        executive_summary (str or None).
    """
    return {
        "executive_summary": output.executive_summary,
        "substance": list(output.substance),
        "decisions": list(output.decisions),
        "commitments": list(output.commitments),
    }


def _format_notion_items_for_prompt(notion_items: list[SourceItem]) -> str:
    """Format Notion SourceItems into readable text for the synthesis prompt.

    Groups page edits and database items separately. Database items are
    grouped by display_context (database name).

    Args:
        notion_items: List of SourceItem objects from Notion ingestion.

    Returns:
        Formatted text block for inclusion in the synthesis prompt.
    """
    if not notion_items:
        return ""

    blocks: list[str] = ["## Notion Activity"]

    page_items = [i for i in notion_items if i.source_type == SourceType.NOTION_PAGE]
    db_items = [i for i in notion_items if i.source_type == SourceType.NOTION_DB]

    if page_items:
        blocks.append(f"### Pages Edited ({len(page_items)})")
        for item in page_items:
            blocks.append(f"- **{item.title}**: {item.content[:200]} {item.attribution_text()}")
        blocks.append("")

    if db_items:
        # Group by database name (display_context)
        db_groups: dict[str, list[SourceItem]] = {}
        for item in db_items:
            group = item.display_context or "Database"
            db_groups.setdefault(group, []).append(item)

        for group_name, items in db_groups.items():
            blocks.append(f"### {group_name} ({len(items)} items)")
            for item in items:
                blocks.append(f"- **{item.title}**: {item.content[:200]} {item.attribution_text()}")
            blocks.append("")

    return "\n".join(blocks)


def synthesize_daily(
    extractions: list[MeetingExtraction],
    target_date: date,
    config: PipelineConfig,
    slack_items: list[SourceItem] | None = None,
    docs_items: list[SourceItem] | None = None,
    hubspot_items: list[SourceItem] | None = None,
    notion_items: list[SourceItem] | None = None,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """Produce daily synthesis from meeting extractions, Slack, Docs, HubSpot, and Notion items.

    Stage 2 of the two-stage pipeline. Takes all per-meeting extractions
    and optional Slack/Docs/HubSpot/Notion SourceItems, builds the synthesis prompt,
    calls Claude, parses the response, and validates for evidence-only language.

    Args:
        extractions: List of MeetingExtraction from Stage 1.
        target_date: The date being synthesized.
        config: Pipeline configuration dict.
        slack_items: Optional list of SourceItem from Slack ingestion.
        docs_items: Optional list of SourceItem from Google Docs ingestion.
        hubspot_items: Optional list of SourceItem from HubSpot ingestion.
        notion_items: Optional list of SourceItem from Notion ingestion.

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
    has_notion = bool(notion_items)

    if not substantive and not has_slack and not has_docs and not has_hubspot and not has_notion:
        logger.info("No substantive extractions, Slack, Docs, or HubSpot items for %s, returning empty synthesis", target_date)
        return empty_result

    # Cross-source dedup for HubSpot items
    deduped_hubspot = _dedup_hubspot_items(hubspot_items or [], substantive, slack_items)

    # Build prompt components
    extractions_text = _format_extractions_for_prompt(substantive)
    slack_items_text = _format_slack_items_for_prompt(slack_items or [])
    docs_items_text = _format_docs_items_for_prompt(docs_items or [])
    hubspot_items_text = _format_hubspot_items_for_prompt(deduped_hubspot)
    notion_items_text = _format_notion_items_for_prompt(notion_items or [])

    # Token budget enforcement: truncate if over budget
    extractions_text, slack_items_text, docs_items_text, hubspot_items_text, notion_items_text, truncated_sources = (
        _estimate_and_truncate(extractions_text, slack_items_text, docs_items_text, hubspot_items_text, notion_items_text)
    )

    transcript_count = len(substantive)
    slack_source_count = len(slack_items) if slack_items else 0
    docs_source_count = len(docs_items) if docs_items else 0
    hubspot_source_count = len(deduped_hubspot)
    notion_source_count = len(notion_items) if notion_items else 0

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
        notion_source_count=notion_source_count,
        extractions_text=extractions_text,
        slack_items_text=slack_items_text,
        docs_items_text=docs_items_text,
        hubspot_items_text=hubspot_items_text,
        notion_items_text=notion_items_text,
        executive_summary_instruction=exec_instruction,
        priority_context=priority_context,
    )

    # Get model settings from config
    model = config.synthesis.model
    max_tokens = config.synthesis.synthesis_max_output_tokens

    # Generate JSON schema from Pydantic model
    schema = prepare_schema_for_claude(DailySynthesisOutput.model_json_schema())

    # Call Claude API with structured output
    client = client or anthropic.Anthropic()
    response = _call_claude_structured_with_retry(
        client, model, max_tokens, prompt, schema
    )

    # Parse and validate structured response
    data = response.content[0].input
    output = DailySynthesisOutput.model_validate(data)

    # Validate evidence-only language on content fields
    content_text = "\n".join(
        [item.content for item in output.substance]
        + [item.content for item in output.decisions]
        + [f"{c.who}: {c.what}" for c in output.commitments]
        + ([output.executive_summary] if output.executive_summary else [])
    )
    violations = validate_evidence_only(content_text)
    if violations:
        logger.warning(
            "Synthesis contains %d evaluative language violation(s) for %s:",
            len(violations),
            target_date,
        )
        for v in violations[:5]:  # Log first 5
            logger.warning("  [%s] '%s' in: ...%s...", v.pattern, v.text, v.context)

    # Convert to backward-compatible dict
    result = _convert_synthesis_to_dict(output)

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
