# PITFALLS: Work Intelligence / Daily Synthesis Pipeline

**Project:** Work Intelligence System (Daily Summarizer)
**Research dimension:** What commonly goes wrong in projects like this
**Date:** 2026-03-23

---

## Summary

This document catalogs pitfalls specific to building a work intelligence pipeline that ingests Google Calendar, Gemini transcripts, and Gong transcripts, processes them through Claude LLM, and outputs structured daily summaries. These are not generic software warnings — they are failure modes observed in this specific domain: API-based data ingestion, transcript parsing, LLM-driven synthesis, noise filtering, temporal aggregation, and Claude Code + Cowork orchestration.

---

## Pitfall 1: Transcript Format Fragility

**Category:** Transcript Parsing
**Severity:** High — silent data loss
**Phase:** Phase 1 (Single-Source MVP)

Gemini and Gong produce transcripts in different formats, and both change their export format without notice. Gemini transcripts arrive as email attachments or Calendar event attachments with inconsistent MIME types, speaker label formatting, and timestamp granularity. Gong transcripts arrive via email with their own structure. Projects that hardcode parsing for a single observed format break silently when the upstream provider ships a change — the parser produces empty or garbled output without raising errors.

**Warning signs:**
- Daily summaries suddenly have fewer items or missing meetings with no pipeline errors
- Speaker attribution disappears or collapses to "Unknown Speaker" across an entire transcript
- Transcript text appears but timestamps or segment boundaries are wrong
- A meeting that definitely happened does not appear in the daily output

**Prevention strategy:**
- Parse transcript format loosely with fallback extraction (regex for speaker labels, then plain text split if structured parse fails)
- Add a validation step after parsing: minimum expected word count per meeting, speaker count > 0, transcript duration roughly matches calendar event duration
- Log raw format fingerprints (MIME type, first 200 chars structure) so format drift is detectable before it causes failures
- Store raw transcript alongside parsed version so reprocessing is possible when format changes

---

## Pitfall 2: Calendar-Transcript Matching Failures

**Category:** API Ingestion / Data Correlation
**Severity:** High — orphaned transcripts, phantom meetings
**Phase:** Phase 1-2

The system depends on correlating calendar events with their transcripts to produce meaningful summaries. This matching is harder than it appears. Calendar event titles rarely match transcript filenames. Recurring meetings produce many events with identical titles. Meeting start times drift from calendar times. Some meetings have transcripts but no calendar events (ad hoc calls). Some calendar events have no transcripts (no-shows, in-person meetings, non-recorded calls). Projects that assume clean 1:1 matching between calendar and transcripts lose data on both sides.

**Warning signs:**
- Unmatched transcripts accumulate in processing logs
- Calendar events appear in summaries with "no content available" despite having been recorded
- Duplicate summary entries for the same meeting (matched to wrong calendar slot)
- Recurring meeting transcripts attributed to the wrong instance

**Prevention strategy:**
- Match on a fuzzy composite key: overlapping time window (not exact match), participant overlap, title similarity score — require 2 of 3 to match
- Build explicit handling for unmatched items: orphan transcripts get summarized with a "no calendar match" flag; calendar events without transcripts are listed as meetings-without-content
- For recurring meetings, use the specific occurrence datetime, not the series ID
- Surface match confidence in the output so Micah can spot mismatches during POC review

---

## Pitfall 3: Gmail/Calendar API Auth Token Decay

**Category:** API Ingestion
**Severity:** Medium — pipeline silently stops producing output
**Phase:** Phase 0 (Cowork Spike) and ongoing

Google OAuth tokens expire and refresh tokens can be invalidated by security policy changes, password resets, or workspace admin actions. In a Claude Code + Cowork execution model, the pipeline runs in a non-interactive context where re-authentication is impossible. Projects that set up auth once and assume it persists discover weeks later that the pipeline has been running against stale or empty data because the API calls were returning 401s that got swallowed.

**Warning signs:**
- Pipeline completes "successfully" but output is empty or contains only calendar events (no transcript content)
- Gmail API returns zero results for a time range that should have emails
- Sudden drop in data volume with no corresponding change in meeting schedule
- Cowork task completes much faster than usual (because it skipped all API calls)

**Prevention strategy:**
- Add an explicit auth health check at pipeline start: make a lightweight API call (e.g., list 1 calendar event) and fail loudly if it returns 401/403
- Include data volume assertions: if today's pipeline processed fewer than N calendar events on a weekday, flag it as anomalous rather than producing a thin summary
- Store the last successful auth timestamp and alert if it exceeds a threshold
- Document the exact re-auth procedure so recovery is fast when it inevitably happens

---

## Pitfall 4: LLM Prompt Drift Toward Evaluative Language

**Category:** LLM Prompt Engineering
**Severity:** High — violates core design constraint
**Phase:** Phase 1 and ongoing

The evidence-only framing constraint (no "performed well," "underperformed," or other evaluative language about people) is a hard requirement, but LLMs naturally tend toward evaluative summarization. When you ask an LLM to synthesize meeting content involving people, it gravitates toward assessments: "Alex provided strong pushback," "the team struggled with alignment," "Sarah effectively mediated." These are judgments dressed as observations. Projects that enforce this constraint only in the initial prompt find it erodes as prompts get refined, context windows fill up, and edge cases accumulate.

**Warning signs:**
- Output contains adjectives applied to people's actions: "effectively," "poorly," "strong," "weak," "impressive"
- Summary frames contributions comparatively: "X contributed more than Y"
- Sentiment language appears: "tension," "frustration," "enthusiasm" attributed to individuals
- Coaching or development language surfaces: "area for growth," "demonstrated improvement"

**Prevention strategy:**
- Include explicit negative examples in the system prompt: "NEVER write: 'Alex pushed back effectively.' INSTEAD write: 'Alex raised three objections to the timeline: [specifics]. The team revised the deadline from March to April.'"
- Add a post-processing validation step that scans output for evaluative patterns (regex or a second LLM pass specifically checking for constraint violations)
- Frame the synthesis prompt around actions and outcomes, not contributions: "What decisions were made?" not "How did people contribute?"
- During POC, manually audit every daily output for evaluative language to calibrate the prompt before automation

---

## Pitfall 5: Noise Domination in Transcript Synthesis

**Category:** Noise Filtering / LLM Prompt Engineering
**Severity:** High — makes output useless
**Phase:** Phase 1-2

Meeting transcripts are approximately 70-80% low-signal content: greetings, scheduling logistics, screen-sharing instructions, "can you hear me," restatements of things already said, and tangential conversation. If the full transcript is passed to the LLM without pre-filtering or the prompt does not aggressively prioritize substance, the synthesis reflects the transcript's distribution: mostly filler. The planning docs identify this as the core engineering challenge ("signal over volume"), and it remains the most common failure mode in these systems.

**Warning signs:**
- Daily summaries read like meeting minutes rather than intelligence (who said what, in order)
- The same information appears multiple times across summary items because multiple people restated it in the meeting
- Summaries are excessively long relative to the number of actual decisions or outcomes
- Reading the summary takes almost as long as attending the meeting would have

**Prevention strategy:**
- Pre-process transcripts before LLM synthesis: strip the first and last 2-3 minutes (logistics/wrap-up), collapse repeated speaker turns, remove filler phrases
- Structure the synthesis prompt as extraction, not summarization: "Extract decisions made, with the specific rationale discussed. Extract commitments with owner and deadline. Extract unresolved questions." This forces the LLM to hunt for signal rather than compress everything proportionally
- Set explicit length constraints per meeting in the prompt: a 30-minute meeting with 3 attendees should produce 3-5 bullet points, not 15
- Include a "significance threshold" instruction: "Only include items that would change someone's understanding of project status, team direction, or open commitments"

---

## Pitfall 6: Temporal Context Collapse in Roll-ups

**Category:** Temporal Aggregation
**Severity:** Medium — degrades value of weekly/monthly outputs
**Phase:** Phase 3

When daily summaries roll up into weekly or monthly intelligence, naive aggregation produces a flat list of everything that happened rather than a narrative with causal threads. "On Monday X was decided. On Wednesday X was revised. On Friday X was abandoned" should become a single story arc, not three disconnected items. Projects that treat temporal roll-ups as concatenation-plus-summarization miss the connective tissue that makes roll-ups more valuable than the sum of their dailies.

**Warning signs:**
- Weekly summaries are just shorter versions of five daily summaries concatenated
- The same topic appears in multiple bullet points across different days without connection
- Monthly narratives lack any sense of progression, trajectory, or resolution
- Roll-ups are significantly longer than they should be because related items are not merged

**Prevention strategy:**
- Tag daily summary items with topic/thread identifiers so roll-ups can group related items across days
- Structure roll-up prompts around threads, not days: "Identify the 3-5 most significant threads from this week. For each, trace the progression from first mention to current status"
- Include explicit instructions to identify reversals, escalations, and resolutions — these are the high-signal moments in a temporal view
- During POC, manually create one weekly roll-up to establish what "good" looks like before automating

---

## Pitfall 7: Cowork/Claude Code Session Reliability

**Category:** Orchestration Model
**Severity:** High — pipeline does not run
**Phase:** Phase 0 (Cowork Spike)

The Claude Code + Cowork orchestration model is unproven for production daily pipelines. Cowork triggers are best-effort, not guaranteed. Claude Code sessions can timeout on long transcripts, hit plan rate limits, or fail to complete if the context window fills up mid-processing. Unlike a cron job on a server, there is no process supervisor, no retry logic, and no persistent state between runs. The planning docs acknowledge this risk and propose a spike to validate, which is correct — but the spike needs to test failure modes, not just happy path.

**Warning signs:**
- Pipeline runs successfully 4 out of 5 days but misses one with no trace of why
- Processing time varies wildly (5 minutes one day, 45 minutes the next) suggesting context window or rate limit issues
- Output is truncated mid-summary, suggesting the session hit a limit
- Cowork task shows as "completed" but no output file was written

**Prevention strategy:**
- The Cowork spike (already planned) must explicitly test: what happens on a day with 8+ meetings? What happens when a single transcript exceeds 50,000 tokens? What happens when the pipeline runs at plan rate limit boundaries?
- Build the pipeline to be idempotent and resumable: if it fails mid-run, re-running it produces the correct output without duplicating work
- Write a completion marker file at the end of each run with metadata (events processed, transcripts parsed, summary items generated) so missing or incomplete runs are detectable
- Have a documented manual fallback: if Cowork fails for 2+ consecutive days, the pipeline can be triggered manually via Claude Code with the same command

---

## Pitfall 8: Gong Email Delivery Parsing Brittleness

**Category:** API Ingestion / Transcript Parsing
**Severity:** Medium — loses an entire transcript source
**Phase:** Phase 1

Gong delivers transcripts via email, which means ingestion depends on parsing email content rather than calling a structured API. Email HTML formatting varies, Gong may change their email templates, and transcript content may be inline, attached, or linked. Projects that parse Gong email transcripts using HTML structure (div classes, table layouts) break when Gong updates their email template. Additionally, Gong emails may arrive hours after the meeting, creating timing mismatches with the daily pipeline run.

**Warning signs:**
- Gong transcripts stop appearing in summaries while Gemini transcripts continue working
- Parsed Gong content contains HTML artifacts or formatting remnants
- Gong transcripts from afternoon meetings consistently missing from same-day summaries (arrived after pipeline ran)

**Prevention strategy:**
- Parse Gong emails with a text-extraction-first approach: strip HTML to plain text, then extract structure, rather than relying on specific HTML element paths
- Handle timing: the pipeline should look back 36 hours for Gong emails (not just "today") to catch late-arriving transcripts
- If Gong offers an API or webhook option, prefer that over email parsing for v2
- Test Gong parsing with 10+ real emails to catalog format variations before building the parser

---

## Pitfall 9: Context Window Exhaustion on Heavy Days

**Category:** LLM Prompt Engineering / Orchestration
**Severity:** Medium — degraded output on the days that matter most
**Phase:** Phase 1-2

The days with the most meetings and longest transcripts are exactly the days where synthesis is most valuable — and exactly the days where the pipeline is most likely to fail. A day with 8 meetings and 6 transcripts could easily produce 200,000+ tokens of raw input. Even with Claude's large context window, stuffing everything into a single prompt degrades output quality (attention dilution) and may exceed limits. Projects that design for average days fail on the days that matter.

**Warning signs:**
- Output quality is noticeably worse on busy days (vaguer, more generic, missing specific details)
- Pipeline errors or timeouts only on days with heavy meeting loads
- Later meetings in the day consistently get thinner coverage than morning meetings (positional bias in long contexts)

**Prevention strategy:**
- Process each meeting transcript individually first (per-meeting extraction), then synthesize the per-meeting outputs into a daily summary — two-stage pipeline, not single-pass
- Set a per-transcript token budget for the extraction stage: if a transcript exceeds the budget, summarize it in chunks before extraction
- On the synthesis stage, feed structured extractions (not raw transcripts) to keep input manageable
- Benchmark with a realistic "worst case" day early in the POC (8+ meetings, 4+ hour-long transcripts)

---

## Pitfall 10: Source Attribution Breaks Under Synthesis

**Category:** LLM Prompt Engineering
**Severity:** Medium — erodes trust in the system
**Phase:** Phase 1-2

The planning docs identify source linking as a trust-building requirement: each summary item should trace back to a specific transcript or calendar event. But when the LLM synthesizes across multiple sources, attribution gets muddled. A decision mentioned in both a meeting transcript and a follow-up email may be attributed to only one source. Worse, the LLM may hallucinate connections between sources or attribute a statement to the wrong meeting. Without reliable attribution, the user cannot verify claims, and the system becomes an unreliable narrator.

**Warning signs:**
- Summary items cite meeting names that do not match any calendar event
- The same information is attributed to different sources on different days
- Source links point to the right meeting but the wrong segment (wrong time, wrong speaker)
- User clicks through to verify a claim and cannot find it in the cited source

**Prevention strategy:**
- Pass source identifiers (meeting title, date, speaker) as structured metadata alongside transcript content, not embedded in prose
- Instruct the LLM to cite sources inline using a consistent format: `[Source: Meeting Title, YYYY-MM-DD]`
- In the per-meeting extraction stage, tag every extracted item with its source before the synthesis stage sees it — this way the synthesis LLM is attributing pre-tagged items, not trying to trace back through raw content
- During POC, manually verify 3-5 source attributions per daily summary to measure accuracy

---

## Phase Mapping Summary

| Pitfall | Primary Phase | Also Relevant In |
|---------|--------------|------------------|
| 1. Transcript Format Fragility | Phase 1 | Ongoing |
| 2. Calendar-Transcript Matching | Phase 1-2 | Ongoing |
| 3. Auth Token Decay | Phase 0 (Spike) | Ongoing |
| 4. Evaluative Language Drift | Phase 1 | Every phase |
| 5. Noise Domination | Phase 1-2 | Every phase |
| 6. Temporal Context Collapse | Phase 3 | Phase 4 |
| 7. Cowork/Claude Code Reliability | Phase 0 (Spike) | Ongoing |
| 8. Gong Email Parsing Brittleness | Phase 1 | Ongoing |
| 9. Context Window Exhaustion | Phase 1-2 | Phase 3 |
| 10. Source Attribution Breaks | Phase 1-2 | Phase 3-4 |

---

## Key Themes Across Pitfalls

**Silent failures are the dominant risk pattern.** Pitfalls 1, 2, 3, 7, and 8 all share the characteristic that the pipeline appears to succeed while producing degraded output. The most important cross-cutting prevention strategy is data volume assertions: every run should validate that it processed a plausible number of events, transcripts, and summary items for the day of week.

**The two-stage pipeline architecture prevents multiple pitfalls simultaneously.** Per-meeting extraction followed by daily synthesis (rather than single-pass processing) mitigates noise domination (5), context window exhaustion (9), and source attribution breaks (10). This architectural choice should be made in Phase 1.

**The POC phase is the right time to catch most of these.** Pitfalls 4, 5, 6, and 10 are all detectable during manual review in Phase 0/1 if the reviewer is looking for them. The prevention strategy for the POC should include an explicit checklist: Does this summary contain evaluative language? Is it mostly noise? Are sources correct? Would this roll up well?

---

*Generated 2026-03-23 for downstream consumption by planning/roadmap agents.*
