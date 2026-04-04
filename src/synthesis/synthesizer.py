"""Stage 2: Daily cross-meeting synthesis via Claude API.

Merges per-meeting extractions into a unified daily intelligence brief
organized by the three core questions: Substance, Decisions, Commitments.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import anthropic

from src.synthesis.models import MeetingExtraction
from src.synthesis.validator import validate_evidence_only

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_OUTPUT_TOKENS = 8192

EXECUTIVE_SUMMARY_INSTRUCTION = """## Executive Summary
[Provide 3-5 sentences summarizing the most significant items from today's meetings. Focus on decisions with broad impact, new commitments with tight deadlines, and substance that changes direction.]

"""

SYNTHESIS_PROMPT = """You are producing a daily intelligence brief. Be concise. Every word must earn its place.

Date: {date}
Number of meetings with transcripts: {transcript_count}

{extractions_text}

{priority_context}

Produce a daily summary with these exact sections:

{executive_summary_instruction}## Substance
One bullet per distinct thing that happened. Keep it concise but include enough context to be useful standalone.
- [What happened] — [Source meeting]

## Decisions
One bullet per decision. Merge duplicates across meetings. Always include who decided.
- [What was decided] — [Who decided] — [Source meeting]

## Commitments
One bullet per action item. ALWAYS include the owner name and deadline. Every commitment must have an owner.
- [What] — [Owner] — [Deadline if stated, or "no deadline"] — [Source meeting]

CRITICAL RULES:
- CONCISE: Each bullet should be 1-2 short sentences max. No filler words.
- CONTEXT: Every bullet must be understandable on its own without reading the full document. Include enough specifics.
- OWNERS: Every commitment MUST name who owns it. Never write a commitment without an owner.
- DEDUPLICATE: If the same topic came up in multiple meetings, write ONE bullet and list both meetings.
- NO PADDING: "Hire HubSpot vendor (<$5K)" not "Team decided to move forward with hiring an external vendor for HubSpot onboarding and professional flow building."
- Source meeting goes at end after an em dash.
- Neutral tone. Facts only.
- If a category has no items, write "No items for this day."
"""


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

        # Extract bullet items (lines starting with -)
        items: list[str] = []
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
    config: dict,
) -> dict:
    """Produce daily synthesis from meeting extractions.

    Stage 2 of the two-stage pipeline. Takes all per-meeting extractions,
    builds the synthesis prompt, calls Claude, parses the response, and
    validates for evidence-only language.

    Args:
        extractions: List of MeetingExtraction from Stage 1.
        target_date: The date being synthesized.
        config: Pipeline configuration dict.

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
    if not substantive:
        logger.info("No substantive extractions for %s, returning empty synthesis", target_date)
        return empty_result

    # Build prompt
    extractions_text = _format_extractions_for_prompt(substantive)
    transcript_count = len(substantive)

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
        extractions_text=extractions_text,
        executive_summary_instruction=exec_instruction,
        priority_context=priority_context,
    )

    # Get model settings from config
    synthesis_config = config.get("synthesis", {})
    model = synthesis_config.get("model", DEFAULT_MODEL)
    max_tokens = synthesis_config.get("synthesis_max_output_tokens", DEFAULT_MAX_OUTPUT_TOKENS)

    # Call Claude API
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
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

    logger.info(
        "Synthesis for %s: %d substance, %d decisions, %d commitments%s",
        target_date,
        len(result["substance"]),
        len(result["decisions"]),
        len(result["commitments"]),
        " (with executive summary)" if result["executive_summary"] else "",
    )

    return result
