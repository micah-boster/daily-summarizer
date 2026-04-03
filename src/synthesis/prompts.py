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
