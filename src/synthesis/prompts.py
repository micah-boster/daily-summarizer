"""Prompt templates for extraction and synthesis pipeline."""

EXTRACTION_PROMPT = """You are a court reporter analyzing a meeting transcript. Extract factual information only.

Meeting: {meeting_title}
Date: {meeting_time}
Participants: {participants}

Transcript:
{transcript_text}

Extract the following categories. For each item, include:
- The factual content (what was said/decided/committed to)
- Which participants were involved
- The stated rationale (only if explicitly stated in the transcript; write "Not stated" if no rationale was given)

Use this exact format for your response:

## Decisions
[For each decision made in the meeting. Skip if none.]
- **Decision:** [what was decided]
- **Participants:** [who was involved]
- **Rationale:** [stated reasoning, or "Not stated"]

## Commitments
[For each task, action item, or commitment. Include owner and deadline if stated.]
- **Commitment:** [what was committed to]
- **Owner:** [who committed]
- **Deadline:** [if stated, otherwise "Not stated"]

## Substance
[Key topics discussed, outcomes, updates, or information shared that would matter if missed. Skip trivial scheduling talk and low-signal chatter.]
- **Item:** [what happened or was discussed]
- **Participants:** [who was involved]
- **Context:** [relevant background if stated]

## Open Questions
[Questions raised but not resolved in this meeting.]
- **Question:** [the unresolved question]
- **Raised by:** [who raised it]

## Tensions
[Disagreements or unresolved tensions between participants. Report facts only -- no judgment.]
- **Tension:** [what the disagreement was about]
- **Participants:** [who disagreed]
- **Status:** [resolved/unresolved]

CRITICAL RULES:
- Report ONLY what was explicitly said. Do not infer, speculate, or editorialize.
- Use neutral language: "Team decided X" not "Team wisely decided X"
- Do not evaluate anyone's performance, attitude, or contribution quality.
- If a category has no items, write "None" under that heading.
- Skip trivial scheduling decisions ("let's meet Tuesday") unless they involve substantive planning.
"""


WEEKLY_THREAD_DETECTION_PROMPT = """You are a court reporter producing a weekly intelligence brief. Analyze the daily summaries below and identify threads -- topics, decisions, or commitments that appear or evolve across multiple days.

Week: {date_range}
Number of daily summaries: {daily_count}

{daily_content}

Produce a weekly thread analysis with these exact sections:

For each thread you identify (aim for 3-5 most significant):

## Thread N: [Thread Title]
**Significance:** [high or medium]
**Status:** [resolved, open, or escalated]
**Tags:** [comma-separated: decision, commitment, substance]
**Progression:** [Chronological narrative arc, e.g., "Monday: concern raised -> Wednesday: options explored -> Thursday: decision locked in"]

For each day this thread appears:
- **[Day Name, Month Day]** (category): [What happened on this day related to this thread]

## Single-Day Items
[Important items that appeared on only one day but are significant enough to highlight. Do NOT force these into threads.]
For each:
- **[YYYY-MM-DD]** (category): [Content]

## Still Open
[Commitments not yet completed, questions not yet answered, unresolved tensions. Track each with its status.]
For each:
- [Description] | **Owner:** [if known] | **Since:** [date first appeared] | **Status:** [waiting, in progress, blocked]

CRITICAL RULES:
- Only link items that genuinely refer to the same topic, decision, or commitment. Do NOT invent connections between unrelated items.
- Single-day items are fine and expected. Not everything forms a thread.
- Rank threads by SIGNIFICANCE, not frequency. A one-time board decision outranks a recurring standup topic.
- Categories (decision, commitment, substance) become tags on thread entries, not organizing sections.
- Use neutral reporter tone: facts only, no editorializing.
- Do not use words like: productive, effective, impressive, excellent, poor, weak, strong, wisely, unfortunately
- Threads should read as mini-stories with an arc, not disconnected bullet points.
- If there are fewer than 3 threads, that's fine. Do not pad.
- "Still Open" must track items from ALL daily summaries that remain unresolved, not just from threads.
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

Produce a monthly narrative with these exact sections:

## Thematic Arcs
For each theme (identify 3-5):

### [Theme Title]
**Trajectory:** [growing, declining, stable, emerging, or resolved]
**Active Weeks:** [comma-separated week numbers, e.g., W14, W15, W16]

[2-3 sentence analytical description of this theme, written in third-person analytical briefing tone. Example: "Hiring pipeline acceleration dominated the first three weeks, with three new roles approved and two offers extended. By week four, focus shifted to onboarding as the first hire started."]

Key moments:
- [Specific significant event or decision within this arc]
- [Another key moment]

## Strategic Shifts
[Notable priority changes or direction shifts observed over the month. Not individual decisions -- patterns of change.]
- [Shift description]

## Emerging Risks
[Concerns that grew over the month or appeared in multiple weeks. Not one-off mentions -- sustained patterns.]
- [Risk description]

## Still Open
[Items unresolved at month end, carried forward from weekly still-open sections.]
- [Item description]

CRITICAL RULES:
- Use analytical third-person tone throughout. Example: "Three themes dominated April: hiring pipeline acceleration, Q2 planning, and partner onboarding."
- This is a strategic briefing, not an operational log. Surface patterns invisible at weekly granularity.
- Do not use words like: productive, effective, impressive, excellent, poor, weak, strong, wisely, unfortunately
- Thematic arcs should span multiple weeks. Single-week themes belong in the weekly summary, not here.
- Metrics provide context for the narrative, not a dashboard. Weave them in naturally.
- Keep to 2-3 pages. This should be readable in about 10 minutes.
"""
