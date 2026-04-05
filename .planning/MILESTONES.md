# Milestones

## v1.0 — Daily Intelligence Pipeline

**Completed:** 2026-04-03
**Phases:** 0-5 (6 phases, 14 plans)

**Delivered:**
- Google Calendar event ingestion
- Meeting transcript extraction (Gemini via Gmail/Calendar, Gong via email)
- Two-stage Claude synthesis (per-meeting extraction → daily cross-meeting synthesis)
- Structured markdown output with source attribution
- Temporal roll-ups (weekly, monthly)
- Slack digest notifications (Block Kit)
- Priority configuration (projects, people, topics)
- Quality tracking and JSON sidecar output
- Evidence-only framing enforced (no evaluative language)

**Key decisions:**
- Python + Claude API (migrated from Claude Code plan limits)
- Flat markdown files for storage
- Two-stage synthesis is architecturally required
- Bounce-only scope for v1

## v1.5 — Multi-Source Expansion

**Completed:** 2026-04-04
**Phases:** 6-12 (7 phases)

**Delivered:**
- Slack message ingestion from curated channels
- HubSpot activity ingestion (deals, contacts, notes)
- Google Docs ingestion
- Cross-source deduplication via LLM
- Source attribution throughout synthesis output
- Multi-source synthesis prompts
- Commitment extraction with structured deadlines
- Pipeline hardening and reliability

**Key decisions:**
- SourceItem as parallel model to NormalizedEvent (not extending)
- runtime_checkable Protocol for SynthesisSource shared interface
- Slack channel discovery + manual curation
- HubSpot: activity-only scope (deals, notes, not full CRM)
- Notion deferred to v1.5.1 due to API complexity

## v1.5.1 — Notion + Performance + Reliability

**Completed:** 2026-04-05
**Phases:** 13-17 (5 phases, 12 plans)

**Delivered:**
- Typed config model with Pydantic validation (Phase 13)
- Claude API structured output migration — json_schema (Phase 14)
- Notion page/database ingestion (Phase 15)
- Slack batch user resolution with disk cache (Phase 16)
- Cache retention policy with auto-cleanup (Phase 16)
- Algorithmic cross-source deduplication pre-filter (Phase 16)
- Async pipeline parallelization — concurrent ingest + extraction (Phase 17)

**Key decisions:**
- httpx for Notion API (no SDK), pinned to Notion-Version 2022-06-28
- Pydantic for both config validation and Claude structured outputs
- Conservative dedup threshold (0.85 title similarity)
- AsyncAnthropic client created inside async_pipeline (not in PipelineContext)
- pytest-asyncio for async test support
