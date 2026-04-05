"""Prompt templates for extraction and synthesis pipeline."""

EXTRACTION_PROMPT = """Extract factual information from this meeting transcript into structured JSON.

Meeting: {meeting_title}
Date: {meeting_time}
Participants: {participants}

Transcript:
{transcript_text}

Use the reasoning field to think through what happened in the meeting before extracting structured data.

For each extracted item:
- content: A single concise factual sentence (15-20 words max)
- participants: First names only of people involved (e.g., ["Sarah", "Mike"])
- rationale: The explicit reason if stated in the transcript, or null if not stated

RULES:
- Facts only. No inference, no editorializing, no evaluation of anyone.
- If a category has no items, leave the list empty.
- Skip trivial scheduling ("let's meet Tuesday") and social chatter.
- Do NOT repeat the same point in multiple categories. Pick the best fit.
- Use first names: "Micah" not "Micah Boster". "Colin" not "Colin Buys".
"""


WEEKLY_THREAD_DETECTION_PROMPT = """You are a court reporter producing a weekly intelligence brief. Analyze the daily summaries below and identify threads -- topics, decisions, or commitments that appear or evolve across multiple days.

Week: {date_range}
Number of daily summaries: {daily_count}

{daily_content}

Use the reasoning field to think through thread connections before populating structured fields.

Populate the following JSON fields:

**threads** (aim for 3-5 most significant):
Each thread has:
- title: Descriptive thread title
- significance: "high" or "medium"
- status: "resolved", "open", or "escalated"
- tags: list of categories like "decision", "commitment", "substance"
- progression: Chronological narrative arc, e.g., "Monday: concern raised -> Wednesday: options explored -> Thursday: decision locked in"
- entries: list of day entries, each with:
  - day_label: "Day Name, Month Day" format (e.g., "Monday, March 30")
  - category: "decision", "commitment", or "substance"
  - content: What happened on this day related to this thread

**single_day_items**: Important items that appeared on only one day but are significant enough to highlight. Do NOT force these into threads. Each with:
- day_label: "Day Name, Month Day" format
- category: "decision", "commitment", or "substance"
- content: Description of the item

**still_open**: Commitments not yet completed, questions not yet answered, unresolved tensions. Each with:
- content: Description of the open item
- owner: Person responsible (or null if unknown)
- since: Date first appeared as YYYY-MM-DD string (or null if unknown)

CRITICAL RULES:
- Only link items that genuinely refer to the same topic, decision, or commitment. Do NOT invent connections between unrelated items.
- Single-day items are fine and expected. Not everything forms a thread.
- Rank threads by SIGNIFICANCE, not frequency. A one-time board decision outranks a recurring standup topic.
- Categories (decision, commitment, substance) become tags on thread entries, not organizing sections.
- Use neutral reporter tone: facts only, no editorializing.
- Do not use words like: productive, effective, impressive, excellent, poor, weak, strong, wisely, unfortunately
- Threads should read as mini-stories with an arc, not disconnected bullet points.
- If there are fewer than 3 threads, that's fine. Do not pad.
- "still_open" must track items from ALL daily summaries that remain unresolved, not just from threads.
"""


MONTHLY_NARRATIVE_PROMPT = """You are a strategic analyst producing a monthly intelligence brief. Synthesize the weekly summaries below into a thematic analysis of the month.

Month: {month_name} {year}
Weeks covered: {weekly_count}

Metrics context:
- Total meetings: {total_meetings}
- Total hours: {total_hours:.1f}
- Total decisions: {total_decisions}
- Top recurring attendees: {top_attendees}

{weekly_content}

This is NOT a longer weekly summary. Do NOT chronologically list what happened each week. Instead, synthesize themes visible only at monthly scale.

Use the reasoning field to think through thematic patterns before populating structured fields.

Populate the following JSON fields:

**thematic_arcs** (identify 3-5 themes):
Each arc has:
- title: Descriptive theme title
- trajectory: "growing", "declining", "stable", "emerging", or "resolved"
- weeks_active: list of ISO week numbers (e.g., [14, 15, 16])
- description: 2-3 sentence analytical description in third-person briefing tone. Example: "Hiring pipeline acceleration dominated the first three weeks, with three new roles approved and two offers extended. By week four, focus shifted to onboarding as the first hire started."
- key_moments: list of specific significant events or decisions within this arc

**strategic_shifts**: Notable priority changes or direction shifts observed over the month. Not individual decisions -- patterns of change. List of description strings.

**emerging_risks**: Concerns that grew over the month or appeared in multiple weeks. Not one-off mentions -- sustained patterns. List of description strings.

**still_open**: Items unresolved at month end, carried forward from weekly still-open sections. Each with:
- content: Description of the open item
- owner: Person responsible (or null if unknown)
- since: Date first appeared as YYYY-MM-DD string (or null if unknown)

CRITICAL RULES:
- Use analytical third-person tone throughout. Example: "Three themes dominated April: hiring pipeline acceleration, Q2 planning, and partner onboarding."
- This is a strategic briefing, not an operational log. Surface patterns invisible at weekly granularity.
- Do not use words like: productive, effective, impressive, excellent, poor, weak, strong, wisely, unfortunately
- Thematic arcs should span multiple weeks. Single-week themes belong in the weekly summary, not here.
- Metrics provide context for the narrative, not a dashboard. Weave them in naturally.
- Keep descriptions concise. This should be readable in about 10 minutes.
"""
