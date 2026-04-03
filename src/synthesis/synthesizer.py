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

SYNTHESIS_PROMPT = """You are a court reporter producing a daily intelligence brief. Synthesize the extracted meeting data below into a single daily summary.

Date: {date}
Number of meetings with transcripts: {transcript_count}

{extractions_text}

Produce a daily summary with these exact sections:

{executive_summary_instruction}## Substance
[What happened of substance today? List specific items, not vague generalities.]
For each item:
- **Item:** [specific thing that happened] (Meeting Title -- Key Participants)

## Decisions
[What decisions were made, by whom, with what rationale?]
For each decision:
- **Decision:** [what was decided] | **Who:** [decision maker(s)] | **Rationale:** [stated reasoning] (Meeting Title -- Key Participants)

## Commitments
[What tasks/commitments were created, completed, or deferred? Include owners and deadlines where stated.]
For each commitment:
- **Commitment:** [what was committed to] | **Owner:** [who] | **Deadline:** [if stated] | **Status:** [created/completed/deferred] (Meeting Title -- Key Participants)

CRITICAL RULES:
- Every item MUST include its source meeting in parentheses: (Meeting Title -- Key Participants)
- When an item appears in multiple meetings, list all sources: (Meeting A -- Sarah; Meeting B -- Mike)
- Use neutral reporter tone: facts only, no editorializing, no evaluating individuals
- Do not use words like: productive, effective, impressive, excellent, poor, weak, strong, wisely, unfortunately
- Merge duplicate items that appeared in multiple meetings into a single item with multiple sources
- If a category has no items across all meetings, write "No items for this day."
- Be specific: "Team decided to delay launch to Q3 due to API dependency" not "Team discussed launch timing"
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
        if not section_text or section_text.strip().lower() == "no items for this day.":
            continue

        # Extract bullet items (lines starting with -)
        items: list[str] = []
        current_item_lines: list[str] = []

        for line in section_text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- **"):
                if current_item_lines:
                    items.append(" ".join(current_item_lines))
                current_item_lines = [stripped[2:]]  # Remove "- " prefix
            elif stripped and current_item_lines:
                current_item_lines.append(stripped)

        if current_item_lines:
            items.append(" ".join(current_item_lines))

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

    prompt = SYNTHESIS_PROMPT.format(
        date=target_date.isoformat(),
        transcript_count=transcript_count,
        extractions_text=extractions_text,
        executive_summary_instruction=exec_instruction,
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
