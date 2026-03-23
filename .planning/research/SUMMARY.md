# Project Research Summary

**Project:** Work Intelligence System (Daily Summarizer)
**Domain:** Personal work intelligence pipeline -- batch ETL with LLM synthesis
**Researched:** 2026-03-23
**Confidence:** MEDIUM-HIGH

## Executive Summary

The Daily Summarizer is a personal batch pipeline that ingests Google Calendar events and meeting transcripts (Gemini via Gmail, Gong via email or API), normalizes them into a common event schema, runs two-stage LLM synthesis (per-meeting extraction, then daily cross-meeting synthesis), and outputs structured markdown files. The architecture is a straightforward four-stage linear pipeline (Ingest, Normalize, Synthesize, Output) orchestrated by Cowork scheduled tasks running Claude Code sessions. The stack is deliberately minimal: Google's official Python client libraries, httpx for Gong, Pydantic for data modeling, Jinja2 for templating, and flat markdown files for storage. No frameworks, no databases, no vector stores, no task queues.

The recommended approach is to validate the Cowork/Claude Code execution model first (Phase 0 spike), then build the pipeline bottom-up starting with data models and output formatting, followed by ingestion, normalization, and synthesis. The two-stage synthesis architecture (per-meeting extraction followed by daily synthesis) is not optional -- it simultaneously solves context window limits, noise filtering, and source attribution, which are the three highest-risk failure modes. The most unconventional aspect is using Claude plan limits instead of API calls for synthesis, which means the Python code handles data movement while the Claude Code session handles reasoning. This boundary between Python and Claude at the normalized data file is the key architectural seam.

The dominant risk pattern is silent failure: the pipeline appears to succeed while producing degraded output due to auth token decay, transcript format changes, or parsing mismatches. Every phase must include data volume assertions and output validation. The secondary risk is evaluative language drift in LLM outputs, which violates the project's core ethical constraint. Both risks are manageable with the prevention strategies identified in research, but they require active monitoring during the POC rather than set-and-forget automation.

## Key Findings

### Recommended Stack

The stack prioritizes simplicity and minimal dependencies. Python 3.12 with uv for package management. No async, no frameworks, no ORMs. See STACK.md for full rationale and version pins.

**Core technologies:**
- **Python 3.12 + uv**: Runtime and package management -- mature, fast, replaces pip/poetry/pyenv in one tool
- **google-api-python-client + google-auth**: Google Calendar and Gmail API access -- official client handles OAuth2 refresh, discovery, pagination
- **httpx**: Gong REST API access (no official SDK exists) -- modern HTTP client, cleaner than requests
- **Pydantic v2**: Data modeling and validation at API boundaries -- converts raw API dicts to typed objects immediately
- **Jinja2**: Markdown template rendering -- separates template iteration from code changes
- **Flat markdown + TOML config**: Storage and configuration -- no database, stdlib tomllib for config

**Critical version note:** Library version pins in STACK.md are based on known stable releases but were not verified against PyPI (web search was unavailable). Run `uv pip index versions <package>` before pinning.

### Expected Features

Research mapped features across six dimensions against the competitive landscape (Otter.ai, Fireflies, Granola, Reclaim.ai, Mem.ai, Fellow.app, Read.ai). See FEATURES.md for full tables.

**Must have (table stakes):**
- Calendar event ingestion (skeleton for everything)
- Meeting transcript ingestion from at least one source
- Structured daily summary with consistent sections
- Evidence-only framing (no evaluative language about people)
- Per-meeting synthesis as building block for daily view
- Decision and task/commitment extraction
- Per-item source attribution with timestamps and participant names
- Noise filtering (80%+ of raw data is filler)
- Weekly roll-up from dailies

**Should have (differentiators):**
- Cross-meeting daily synthesis (no competitor does this -- the core value proposition)
- Temporal roll-ups with evidence chains (weekly, monthly, quarterly)
- Personnel evidence collection with strict ethical guardrails
- Incremental ingestion (process only new data since last run)
- Multiple output tiers (30-second skim vs. 5-minute read vs. deep dive)
- Structured data sidecar (JSON alongside markdown for downstream querying)

**Defer (v2+):**
- Slack ingestion (highest volume, highest complexity, explicitly out of scope for v1)
- Counterfactual awareness (novel but requires historical baseline)
- Substance calibration / learned preferences (Phase 5 per planning docs)
- Obsidian-native output with wikilinks and backlinks
- Interactive query interface
- Migration from plan limits to Anthropic API

### Architecture Approach

A four-stage linear batch pipeline: Ingest, Normalize, Synthesize, Output. Each stage has a defined input/output contract. The Python code owns data movement (stages 1, 2, 4). The Claude Code session owns reasoning (stage 3). The boundary is a normalized data file that Python writes and Claude reads. See ARCHITECTURE.md for component definitions and data flow diagrams.

**Major components:**
1. **Orchestrator (main.py)** -- Entry point triggered by Cowork; calls stages in sequence; handles errors and completion reporting
2. **Ingestion Layer (ingest/)** -- Per-source modules for Google Calendar and Gmail transcripts; each module is independent and idempotent
3. **Normalization Layer (normalize/)** -- Maps heterogeneous raw data to NormalizedEvent schema; links transcripts to calendar events; filters noise; deduplicates
4. **Synthesis Layer (synthesize/)** -- Two-stage LLM processing: per-meeting extraction then daily synthesis; prompt templates stored as separate files for rapid iteration
5. **Output Layer (output/)** -- Renders DailySynthesis to markdown via Jinja2 templates; writes to date-based directory structure; optionally caches raw data

### Critical Pitfalls

Ten pitfalls identified, with five at high severity. See PITFALLS.md for full details and warning signs.

1. **Transcript format fragility** -- Gemini and Gong change export formats without notice. Prevention: parse loosely with fallback extraction, validate word counts and speaker counts, store raw alongside parsed.
2. **Calendar-transcript matching failures** -- No clean 1:1 match between calendar events and transcripts. Prevention: fuzzy composite matching (time window + attendee overlap + title similarity, require 2 of 3), surface match confidence in output.
3. **Cowork/Claude Code session reliability** -- Unproven for production daily pipelines; best-effort triggers, no retry logic. Prevention: validate in Phase 0 spike with failure mode testing (not just happy path), build idempotent/resumable pipeline, write completion markers.
4. **Evaluative language drift** -- LLMs naturally gravitate toward judgments about people. Prevention: explicit negative examples in prompts, post-processing validation scan, frame prompts around actions/outcomes not contributions.
5. **Noise domination in synthesis** -- 70-80% of transcript content is filler. Prevention: two-stage pipeline (per-meeting extraction then daily synthesis), structure prompts as extraction not summarization, set length constraints per meeting.

## Implications for Roadmap

### Phase 0: Cowork Spike and Auth Validation
**Rationale:** The execution model (Cowork + Claude Code for daily automation) and Google OAuth auth flow are the two existential risks. If either fails, the project architecture changes fundamentally. Validate before building anything.
**Delivers:** Confirmed Cowork scheduling reliability, working Google OAuth token with auto-refresh, documented re-auth procedure, understanding of plan-limit constraints (context window, rate limits, session timeouts).
**Addresses:** Auth health check, execution model validation
**Avoids:** Pitfall 3 (auth token decay), Pitfall 7 (Cowork reliability)

### Phase 1: Data Models, Output, and Single-Source Ingestion
**Rationale:** Build from the inside out. Data models are the foundation everything depends on. Output writer enables testing with mock data immediately. Calendar ingestion is the simplest source and provides the meeting skeleton.
**Delivers:** Pydantic models (NormalizedEvent, DailySynthesis), markdown output writer with Jinja2 templates, working Google Calendar ingestion, date-based file structure.
**Addresses:** Calendar event ingestion, structured markdown output, consistent naming
**Avoids:** Pitfall 5 (noise) by establishing extraction-oriented data models from the start

### Phase 2: Transcript Ingestion and Normalization
**Rationale:** Transcripts are the primary content source. Normalization (linking transcripts to calendar events, deduplication, noise filtering) is the critical data quality layer. This phase will surface the hardest edge cases.
**Delivers:** Gmail transcript ingestion (Gemini format first, Gong email fallback second), normalization pipeline with calendar-transcript linking, noise filtering, raw data caching for debugging.
**Addresses:** Transcript ingestion, deduplication, noise filtering, cross-source event correlation (basic)
**Avoids:** Pitfall 1 (format fragility) via loose parsing + validation, Pitfall 2 (matching failures) via fuzzy composite matching, Pitfall 8 (Gong parsing) via text-extraction-first approach

### Phase 3: Two-Stage Synthesis Pipeline
**Rationale:** This is the core value delivery. Depends on ingestion and normalization being solid. The two-stage approach (per-meeting extraction then daily synthesis) is architecturally required to handle context windows, noise, and attribution simultaneously.
**Delivers:** Per-meeting extraction with source-tagged items, daily cross-meeting synthesis answering the three core questions (substance, decisions, commitments), evidence-only output with source attribution, prompt templates as separate iterable files.
**Addresses:** Structured daily summary, decision extraction, task/commitment extraction, per-item source linking, evidence-only framing, per-meeting synthesis, cross-meeting synthesis
**Avoids:** Pitfall 4 (evaluative language) via prompt guardrails + validation, Pitfall 5 (noise domination) via extraction-oriented prompts, Pitfall 9 (context window exhaustion) via two-stage architecture, Pitfall 10 (attribution breaks) via pre-tagged source items

### Phase 4: Temporal Roll-Ups
**Rationale:** Weekly and monthly roll-ups are the temporal composability layer that differentiates this from per-meeting tools. Depends on having several weeks of daily summaries to work with.
**Delivers:** Weekly roll-up from 5 dailies (thread-based, not concatenation), topic/thread tagging on daily items, monthly narrative with progression arcs.
**Addresses:** Weekly summary, consistent structure across time horizons, monthly narrative with themes, theme extraction
**Avoids:** Pitfall 6 (temporal context collapse) via thread-based roll-up prompts instead of day-based concatenation

### Phase 5: Feedback, Refinement, and Graduation
**Rationale:** Once the pipeline runs reliably and produces useful output, add lightweight feedback mechanisms and consider graduation from plan limits to API.
**Delivers:** Explicit priority configuration, quality metrics tracking, structured data sidecar (JSON), optional Anthropic API migration path.
**Addresses:** Manual correction, prompt iteration, explicit priority config, structured data sidecar, thumbs up/down feedback
**Avoids:** Over-engineering feedback loops before the core synthesis quality is proven

### Phase Ordering Rationale

- **Phase 0 before everything** because the execution model is unproven. Building on Cowork + Claude Code without validating it is the single biggest project risk.
- **Models and output before ingestion** because having the output layer working enables testing every subsequent phase with mock data. This is counterintuitive but architecturally sound -- ARCHITECTURE.md recommends this explicitly.
- **Ingestion before synthesis** because synthesis quality depends entirely on data quality. Getting clean, linked, deduplicated data is harder than writing prompts.
- **Two-stage synthesis as a single phase** because splitting per-meeting extraction from daily synthesis into separate phases would leave the system in a half-useful state.
- **Roll-ups after several weeks of dailies** because you need real accumulated data to build and test temporal aggregation. Do not build roll-ups on synthetic data.
- **Feedback last** because learning loops are premature until the base synthesis is good enough to be worth improving incrementally.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 0:** Cowork scheduling capabilities, Claude Code session limits, plan rate limit behavior under sustained daily use. This is uncharted territory -- no established patterns exist.
- **Phase 2:** Gemini transcript format specifics (MIME types, attachment structure), Gong email template structure. Need real sample data to finalize parsers.
- **Phase 3:** Prompt engineering for extraction-oriented synthesis, optimal two-stage prompt design. This will require iterative experimentation, not upfront research.

Phases with standard patterns (skip deep research):
- **Phase 1:** Google Calendar API, Pydantic modeling, Jinja2 templating, file I/O -- all well-documented with established patterns.
- **Phase 4:** LLM-based summarization of structured text -- standard pattern, though thread-tracking is novel.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Library choices are well-reasoned; exact version pins need PyPI verification (web search was unavailable during research) |
| Features | HIGH | Thorough competitive analysis with clear table-stakes vs. differentiator distinctions; dependency graph is sound |
| Architecture | HIGH | Four-stage linear pipeline is a proven pattern for batch ETL; component boundaries are clean and well-defined |
| Pitfalls | HIGH | Domain-specific, actionable, with concrete warning signs and prevention strategies; correctly identifies silent failure as the dominant risk pattern |

**Overall confidence:** MEDIUM-HIGH

The architecture and feature research are strong. The main confidence gap is the Cowork/Claude Code execution model, which is genuinely novel and cannot be validated through research alone -- it requires the Phase 0 spike. Secondary gap is exact library versions, which is a quick verification task.

### Gaps to Address

- **Cowork scheduling reliability:** No documentation or community evidence on using Cowork for production daily batch pipelines. Phase 0 spike is the only way to validate. Must test failure modes, not just happy path.
- **Token cost per day:** The "zero incremental cost" constraint (plan limits) depends on daily processing fitting within plan rate limits. A day with 8+ meetings could stress this. Needs benchmarking in Phase 0.
- **Gemini transcript format specifics:** Research could not verify current Gemini transcript delivery format (MIME type, attachment vs. inline, speaker label structure). Need 5-10 real samples before building the parser.
- **Gong API vs. email access:** Whether Micah has Gong API access (requires admin privileges) or must use the email delivery fallback affects Phase 2 architecture. Determine before Phase 2 planning.
- **Library version pins:** All version minimums in STACK.md are estimates. Run `uv pip index versions` for each package before creating pyproject.toml.

## Sources

### Primary (HIGH confidence)
- Planning documents: PROJECT.md, architecture decisions, feature requirements from the project planning directory
- Python ecosystem knowledge: Pydantic v2, Google API client libraries, httpx, Jinja2, pytest, ruff -- well-established tools with extensive documentation
- Batch ETL pipeline patterns: standard four-stage architecture is widely documented and proven

### Secondary (MEDIUM confidence)
- Google OAuth2 for personal/desktop applications: well-documented but specific behavior in non-interactive (Cowork) context needs validation
- Gong REST API: documented at developers.gong.io but access requirements and rate limits need verification against Micah's account
- Competitive product features (Otter.ai, Fireflies, Granola, etc.): based on publicly available feature lists, not hands-on testing

### Tertiary (LOW confidence)
- Cowork + Claude Code as production scheduler: no external documentation or community evidence; entirely dependent on Phase 0 spike validation
- Gemini transcript delivery format: inferred from general Google Workspace patterns, not verified against current behavior
- Library version numbers: based on known releases as of early 2026, not verified against PyPI during this research session

---
*Research completed: 2026-03-23*
*Ready for roadmap: yes*
