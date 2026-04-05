# Work Intelligence Platform: Multi-Version Roadmap

**Updated:** April 3, 2026

---

## Version Summary

| Version | Name | Core Capability | Status |
|---------|------|----------------|--------|
| v1.0 | Daily Intelligence | Calendar + transcript ingestion, synthesis, Slack/MD output | **Done** |
| v1.5 | Expanded Ingest | Slack, HubSpot, Docs, Notion as data sources; improved synthesis | Planned |
| v2.0 | Entity Layer | Partners, people, initiatives — discovery, attribution, scoped views | Planned |
| v3.0 | Action Layer | Draft responses, review queue, send via Slack/email | Planned |
| v4.0 | Web Interface | Local-first UI for everything; hostable later | Planned |

---

## v1.0 — Daily Intelligence (Complete)

What's built:
- Google Calendar event ingestion
- Meeting transcript extraction (email + calendar attachments)
- Claude-powered daily synthesis (decisions, commitments, action items, themes)
- Temporal roll-ups (weekly, monthly)
- Slack digest (Block Kit, condensed)
- Markdown detailed output
- Priority-aware configuration
- Quality tracking

---

## v1.5 — Expanded Ingest

**Goal:** Broaden the data surface so synthesis sees the full picture, not just meetings.

### New Data Sources

| Source | What to Capture | Priority |
|--------|----------------|----------|
| **Slack** | Messages from curated channel list; discovery-based channel selection with manual add | High |
| **HubSpot** | Deal activity, contact notes, stage changes, tasks | High |
| **Google Docs** | Documents created/edited that day; extract key content | Medium |
| **Notion** | Page updates, database changes relevant to tracked initiatives | Medium |

### Key Decisions
- **Channel selection**: System discovers active channels from history, user curates list, can explicitly add new ones
- **HubSpot scope**: Activity logs, deal changes, and notes — not the full CRM dump
- **Dedup**: Cross-source deduplication (a meeting discussed in Slack, noted in email, and logged in HubSpot = one event)
- **Synthesis upgrade**: Prompts updated to handle multi-source input and cross-reference between sources

### What Changes
- New ingestion modules per source
- Normalization layer (common event format across all sources)
- Synthesis prompts get source-attribution ("per Slack #channel" / "per HubSpot deal")
- Config file grows: channel list, HubSpot filters, Doc/Notion scoping rules

---

## v2.0 — Entity Layer

**Goal:** Everything is attributed to partners, people, and initiatives. You can ask "what's happening with Affirm?" or "what does Colin owe me?" and get a sourced answer.

### Entity Model

| Entity Type | Examples | Key Attributes |
|-------------|----------|---------------|
| **Partner** | Affirm, Cherry, Oportun | Open items, decisions, AIs, contacts, deal stage |
| **Person** | Colin, Sarah, external contacts | Commitments to/from, interaction history, role |
| **Initiative** | MSA renegotiation, Q2 launch, new pricing model | Status, owners, related decisions, blockers |

### How It Works

1. **Discovery engine** mines accumulated summaries + source data to propose entities
2. User confirms/rejects/merges proposed entities
3. User can explicitly add entities at any time ("start tracking Cardless as a partner")
4. Every synthesis item gets attributed: decisions → who made them + which entity; commitments → owner + entity; action items → assignee + entity
5. Entity merge proposals: "Colin" in meeting + "Colin R." in Slack + "colin@partner.com" in email → proposed merge, user confirms

### Scoped Views
- **Partner view**: All open items, recent decisions, commitments, action items, interaction timeline
- **Person view**: What they owe you, what you owe them, recent interactions, key quotes
- **Initiative view**: Current status, owners, blockers, decision history, next steps

### Storage
- Entity registry (YAML or SQLite)
- Attribution index linking synthesis items → entities
- Scoped query engine

---

## v3.0 — Action Layer

**Goal:** Move from "know what happened" to "act on what happened." Draft responses and queue them for human approval before sending.

### Draft Queue (Superhuman-style)
- System proposes draft responses based on context (commitments made, follow-ups needed, questions asked)
- Drafts land in a review queue
- User can: approve as-is, edit then send, reject, snooze
- **Nothing sends without explicit human approval**

### Supported Channels
| Channel | Capability |
|---------|-----------|
| **Email** | Draft reply to thread, new compose |
| **Slack** | Draft message to channel or DM |

### Context-Aware Drafting
- Drafts reference the source context ("Following up on our discussion in Tuesday's account review...")
- Tone matches the channel (formal for email, casual for Slack)
- Includes relevant entity context from v2

### Architecture Notes
- Draft store with status tracking (proposed → reviewed → approved → sent → confirmed)
- Send via Gmail API and Slack API
- Audit log of everything sent

---

## v4.0 — Web Interface

**Goal:** A clean, functional, modern, professional UI to manage the entire platform.

### Core Views
| View | What It Shows |
|------|--------------|
| **Dashboard** | Today's summary, pending drafts, open items count, upcoming meetings |
| **Daily/Weekly/Monthly** | Browse temporal summaries with full detail |
| **Entity Browser** | Search and browse partners, people, initiatives with scoped views |
| **Draft Queue** | Pending responses — approve, edit, reject, snooze |
| **Settings** | Source config, channel lists, entity management, priority config |

### Technical Approach
- **Phase 1**: Local-only (localhost), Python backend + modern JS frontend
- **Phase 2**: Hostable (auth layer, deployment, mobile-responsive)
- API-first backend so the UI is just one consumer
- All current CLI/script functionality exposed via API

### Design Principles
- Information density over whitespace — you're a power user
- Keyboard navigable
- Fast — no loading spinners for local data
- Entity-centric navigation (click a partner name anywhere → scoped view)

---

## Cross-Cutting Concerns

### Privacy & Security
- All data stays local in v1-v3; hosting in v4 adds auth
- Configurable exclusion rules (skip HR channels, legal threads)
- No automated sending without human approval (ever)

### Cost Management
- Sonnet for daily synthesis, Opus for roll-ups and complex queries
- Cache aggressively — don't re-process unchanged data
- Token budget tracking per run

### Migration Path
- Each version builds on the last, no rewrites
- v1 → v1.5: add ingest modules, update prompts
- v1.5 → v2: add entity layer on top of existing synthesis
- v2 → v3: add action layer consuming entity context
- v3 → v4: wrap everything in a web UI via API layer

---

## Deferred Ideas (Captured, Not Scheduled)
- Relationship mapping / org chart inference
- Sentiment and energy tracking per interaction
- Knowledge graph construction across entities
- Counterfactual awareness ("what didn't happen that should have")
- Team-facing version (not just personal)
- Snowflake/BI correlation ("did my calls affect account health?")
- Obsidian vault integration
- Mobile app
