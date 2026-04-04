# Personal Intelligence Platform — Multi-Version Plan

## Vision

A personal intelligence platform that ingests work data, synthesizes it into actionable intelligence, attributes it to the entities that matter (partners, people, initiatives), and enables action — all through a clean web interface.

## Version Summary

| Version | Theme | Core Deliverable |
|---------|-------|-----------------|
| v1 | Daily Intelligence | ✅ Pipeline ingests calendar + transcripts, produces daily/weekly/monthly summaries |
| v1.5 | Ingestion Hardening | Broader data capture (Slack, Drive transcripts), reliability improvements |
| v2 | Entity Layer | Partners, people, and initiatives as first-class objects with attributed data |
| v3 | Action Layer | Draft and queue responses via Slack and email from context |
| v4 | Web Interface | Modern UI to browse entities, review intelligence, manage drafts, and take action |

---

## v1 — Daily Intelligence ✅ COMPLETE

What we shipped:
- Google Calendar + Gmail/Drive transcript ingestion
- Two-stage LLM synthesis (per-meeting extraction → daily cross-meeting synthesis)
- Daily, weekly, and monthly roll-ups
- Slack notifications with executive digest
- Priority configuration and quality tracking
- JSON sidecar for programmatic access

---

## v1.5 — Ingestion Hardening

**Goal**: Broader, more reliable data capture before building the entity layer on top.

| Phase | What | Why |
|-------|------|-----|
| 1 | Google Calendar transcript attachments | Gemini attaches transcripts to calendar events post-meeting; currently we only search Gmail/Drive. This catches meetings where you're not the organizer. |
| 2 | Slack channel ingestion | Monitor key channels (partner channels, project channels) as a data source. Many decisions and AIs happen in Slack, not meetings. |
| 3 | Transcript source consolidation | Unified transcript model that handles Gemini (calendar), Gemini (email), Gong, and Slack threads with deduplication. |
| 4 | Backfill tooling | Run pipeline against historical date ranges to seed entity data for v2. |

**Exit criteria**: Pipeline reliably captures 90%+ of work-relevant communications across calendar, email, and Slack.

---

## v2 — Entity Layer

**Goal**: Partners, people, and initiatives become first-class objects. Every synthesis item is attributed to one or more entities. You can ask "show me everything about Cardless" or "what does Colin owe me?"

### Data Model

```
Partner (e.g., Cardless, Lendable, Affirm)
├── Decisions (attributed from synthesis)
├── Commitments / Action Items (open, completed, overdue)
├── Open Questions
├── Key People (internal + external contacts)
├── Monitored Channels (Slack channels, email threads)
└── Timeline (chronological activity feed)

Person (e.g., Colin, Yuka, Gabe)
├── Commitments they own (what do they owe?)
├── Commitments owed to them
├── Decisions they participated in
├── Meeting frequency / last interaction
└── Partner associations

Initiative (e.g., HubSpot Migration, Reporting Standardization, Delaware Event)
├── Status (active, paused, completed)
├── Decisions
├── Commitments
├── People involved
├── Partner associations
└── Timeline
```

### Phases

| Phase | What | Why |
|-------|------|-----|
| 1 | Entity registry + YAML config | Define partners, people, initiatives with aliases and metadata. Manual to start — no magic entity detection yet. |
| 2 | Attribution engine | Post-synthesis pass that links each decision/commitment/substance item to entities using name matching, meeting title patterns, and channel associations. |
| 3 | Entity-scoped queries | CLI commands: `entity show cardless`, `entity commitments --owner colin --status open`, `entity timeline hubspot-migration` |
| 4 | Entity-aware synthesis | Synthesis prompt gets entity context ("Cardless is a partner, current status: onboarding, launch target May 1"). Produces better, more contextualized output. |
| 5 | Stale commitment tracking | Flag commitments past deadline, surface "aging" items in daily digest. "Colin's 10 account plans were due last week." |

**Exit criteria**: Running `entity show cardless` returns a complete, accurate picture of all decisions, commitments, open questions, and people — sourced from accumulated daily summaries.

---

## v3 — Action Layer

**Goal**: Move from "here's what happened" to "here's what you should do about it." Draft and queue Slack messages and emails from synthesized context.

### Phases

| Phase | What | Why |
|-------|------|-----|
| 1 | Draft generation engine | Given an entity + context (e.g., overdue commitment, open question), generate a draft message with appropriate tone, context, and ask. |
| 2 | Outbox queue | Drafts are stored, reviewable, editable. Nothing sends without explicit approval. |
| 3 | Slack send integration | Send approved drafts to Slack channels or DMs via API (not webhooks). |
| 4 | Email send integration | Send approved drafts via Gmail API. |
| 5 | Suggested actions | After daily synthesis, system proposes 3-5 actions: "Follow up with Colin on OKRs (2 days overdue)", "Reply to Gabe re: Corkcard meeting scheduling." User approves, edits, or dismisses. |

**Exit criteria**: After reviewing the daily digest, you can approve 3 suggested follow-ups and they land in the right Slack channels / inboxes within 60 seconds.

---

## v4 — Web Interface

**Goal**: A clean, modern, professional web app that replaces the CLI + markdown files as the primary interface.

### Core Views

| View | What it shows |
|------|--------------|
| **Daily Dashboard** | Today's digest (substance, decisions, commitments tables). Quick actions. Upcoming meetings with prep context. |
| **Entity Browser** | List of partners/people/initiatives with status indicators. Click through to entity detail. |
| **Entity Detail** | Timeline, open items, key people, recent decisions. Action buttons (draft follow-up, mark complete). |
| **Outbox** | Queued drafts with preview, edit, approve/dismiss. Send history. |
| **Weekly/Monthly** | Roll-up views with thread visualization and trend indicators. |
| **Search** | Full-text search across all synthesized content with entity/date/type filters. |

### Tech Stack (TBD — decide during planning)

Likely candidates:
- **Backend**: FastAPI (Python, matches existing codebase)
- **Frontend**: React or Next.js (modern, component-based)
- **Database**: PostgreSQL (replaces flat files, supports entity queries)
- **Auth**: Single-user for now, OAuth if ever shared

### Phases

| Phase | What | Why |
|-------|------|-----|
| 1 | API layer | FastAPI wrapping existing pipeline + entity queries. JSON endpoints for all data. |
| 2 | Database migration | Move from flat markdown files to PostgreSQL. Keep markdown as export format. |
| 3 | Daily dashboard + entity browser | Core read-only views. |
| 4 | Entity detail + timeline | Deep-dive views with full context. |
| 5 | Outbox + action UI | Draft review, edit, approve, send. |
| 6 | Search + filtering | Full-text search, date ranges, entity filters. |
| 7 | Polish + mobile | Responsive design, keyboard shortcuts, notification preferences. |

**Exit criteria**: You open the app each morning, review the daily digest, drill into 2-3 entities, approve follow-up drafts, and close it — all in under 10 minutes.

---

## Sequencing Rationale

```
v1 (done) → v1.5 → v2 → v3 → v4
   ↓          ↓      ↓      ↓      ↓
 "What      "More   "About  "Do    "See and
  happened"  data"   whom"  something" manage"
```

- **v1.5 before v2**: Entity attribution is only as good as the data it attributes. Slack ingestion alone will dramatically improve coverage.
- **v2 before v3**: You can't draft a good follow-up without entity context. "What does Colin owe me?" must work before "Draft a reminder to Colin."
- **v3 before v4**: The action model needs to be proven in CLI before building UI around it. Cheaper to iterate on the logic.
- **v4 last**: UI is the most expensive to change. Build it once the data model and workflows are stable.

---

## Open Questions for Micah

1. **Entity bootstrap**: Do you want to manually define the initial partner/people/initiative list, or should the system propose entities from accumulated data?
2. **Slack scope**: Which channels should be monitored? All channels you're in, or a curated list?
3. **Action approval model**: Review each draft individually, or batch-approve a morning set?
4. **Web hosting**: Local-only (localhost), or deployed somewhere accessible from phone/any device?
5. **Timeline**: Any hard deadlines or priority order preferences within versions?
