# Work Intelligence System: Architecture Decision Guide

**Purpose:** Work through these questions systematically to lock down architecture decisions before building. Organized by decision domain, with dependencies noted. Answer these roughly in order — later sections depend on earlier ones.

---

## A. Scope & Intent

These questions define the boundaries of what you're building and who it serves. Everything downstream flows from these answers.

**A1.** Is this a personal tool (your data, your synthesis, only you see output), or does it eventually serve your team or organization? If team-facing, which outputs are shared vs. private?

**A2.** Is this Bounce.AI-only, or does it need to span multiple professional contexts (Nighthawk, advisory work, TJ Angels, etc.)? If multi-context, do summaries stay siloed or can you query across them?

**A3.** What's the primary persona you're building for — yourself as an individual contributor, yourself as a manager of people, or yourself as an executive reporting upward? These emphasize different outputs.

**A4.** How do you envision consuming the output day-to-day? Reading a morning digest? Querying on demand? Both? Where does it show up — email, Slack, Obsidian, a dedicated UI?

**A5.** Is there a specific near-term event that would validate this system's value? (e.g., "If I had this running by Q2 review season, I could produce evidence-backed evaluations for my team.") Having a concrete target shapes prioritization.

**A6.** What's your tolerance for imperfection in v1? Are you comfortable with a system that gets 70% of the signal right and requires manual correction, or does it need to be reliable enough to trust without review?

---

## B. Data Sources & Access

These questions map what's available, what's accessible, and what's worth ingesting.

**B1.** For each source, confirm API access availability and any authentication constraints:

| Source | Questions to Answer |
|--------|-------------------|
| **Gmail** | Which Google Workspace account? Do you have API access or does IT control OAuth scopes? Are call transcripts from a specific tool (Gong, Fireflies, Otter, Google Meet auto-transcription, etc.)? What format are they in — email body, attachment, link to external platform? |
| **Slack** | Which workspace(s)? Do you have admin-level API access or user-level only? Are there rate limits on history retrieval? What's the message retention policy? |
| **HubSpot** | Which HubSpot instance? API key or OAuth? Which objects matter most — contacts, deals, activities, notes, meetings? |
| **Notion** | Which workspace? API integration available? What's the structure — databases, pages, or both? What role does Notion play vs. other tools (is it the source of truth for anything)? |
| **Google Drive** | Same Workspace account as Gmail? Are you tracking document creation/edits, or do you need to read document contents? |
| **Google Calendar** | Confirm this is in scope (recommended). Same Workspace account? Do you need to ingest other people's calendars or just yours? |

**B2.** For each source, what's the volume profile? Roughly how many messages/emails/transcripts/updates per day? This drives cost estimation and processing architecture.

**B3.** Are there sources you'd want to add later that should influence architecture now? Examples: Linear/Jira (engineering tickets), Snowflake (operational metrics), Loom (async video), WhatsApp/iMessage (if you conduct business there).

**B4.** Which source do you believe carries the highest signal-to-noise ratio for your daily work? Rank them if you can. This determines Phase 1 MVP scope.

**B5.** Are there specific channels, labels, folders, or categories within each source that are high-signal vs. noise? For example, in Slack: which 3-5 channels contain 80% of the substantive conversation? In Gmail: are transcripts tagged or filterable?

**B6.** Do any sources overlap significantly? (e.g., meeting notes appear in both Notion and Gmail as transcripts.) How should the system handle deduplication — prefer one source, merge, or flag conflicts?

---

## C. Processing & Synthesis

These questions define how raw data becomes structured intelligence.

**C1.** For the 10 daily questions in the planning doc, rank them by priority. If the system could only answer 3-4 well in v1, which ones? This focuses prompt engineering effort.

**C2.** How granular should the "substance" filter be? Consider these examples from a typical day:

   a. A 45-minute client QBR where a renewal timeline was discussed
   b. A 15-minute standup where someone mentioned a blocker
   c. A Slack thread debating an internal process change
   d. An email confirming a meeting time

   Which of these make the cut? Where's the threshold?

**C3.** For the decision log: what constitutes a "decision" worth capturing? Only formal decisions with clear ownership, or also informal consensus moments ("we agreed in Slack to push the launch")? How do you handle tentative vs. final decisions?

**C4.** For the personnel/team dimension: who are the people you need to track? Just direct reports, or also cross-functional collaborators, clients, and leadership? Is there a maximum number of individuals the system should maintain profiles for?

**C5.** Should the system attempt to infer your emotional/energy state from communication patterns, or is that out of scope? (e.g., shorter responses late in the day, terse Slack messages during high-pressure periods.)

**C6.** How should the system handle confidential or sensitive content? Options:

   a. Exclude certain channels/labels/folders entirely from ingestion
   b. Ingest everything but flag sensitive content for manual review before it enters the summary
   c. Ingest and summarize everything, relying on the system being private to you
   d. Different handling for different sensitivity levels

**C7.** When the system encounters ambiguity (e.g., unclear whether something was a decision or just a discussion), should it include it with a confidence flag, exclude it, or ask you?

**C8.** For meeting transcripts specifically: do you want a per-meeting summary in addition to the daily rollup? Or is the daily synthesis sufficient, with the ability to drill into a specific meeting on demand?

---

## D. Storage & Data Model

These questions determine where intelligence lives and how it's structured for retrieval.

**D1.** What's the primary storage destination? Options, not mutually exclusive:

   a. **Obsidian vault** — aligns with your second brain, good for narrative/markdown, weak for structured queries
   b. **Postgres or SQLite** — strong for structured queries, tagging, cross-referencing; requires a separate read interface
   c. **Vector database (Pinecone, Chroma, pgvector)** — enables semantic search ("find everything related to X"), adds complexity
   d. **Notion** — if it's already your team's workspace, colocating intelligence there reduces friction
   e. **Hybrid** — structured DB for queryability + Obsidian/Notion for human-readable output

**D2.** What's the data retention policy? For each layer:

   a. **Raw inputs** (transcripts, Slack exports, emails): Keep forever? Delete after synthesis? Keep for N days?
   b. **Daily summaries**: Permanent record?
   c. **Roll-ups** (weekly/monthly/quarterly): Permanent?
   d. **Per-person profiles**: Retained indefinitely or reset on some cycle?

**D3.** What entities need to be first-class objects in the data model? Likely candidates:

   a. People (with roles, teams, relationships)
   b. Projects / Accounts / Clients
   c. Decisions (with status: proposed, made, revisited)
   d. Themes / Topics (recurring threads)
   e. Action items (with owner, deadline, status)
   f. Meetings (as a container linking to transcripts, attendees, outcomes)

   Which of these are essential vs. nice-to-have for v1?

**D4.** Do you need to link back to source material? (e.g., "This decision was captured in [this Slack thread] and [this meeting transcript]".) Source linking adds complexity but dramatically increases trust in the system's outputs.

**D5.** If using Obsidian, what's the vault structure? A daily note per day? Separate folders for people, projects, decisions? How does this integrate with your existing vault organization?

---

## E. Temporal Aggregation & Roll-Ups

These questions define how daily intelligence compounds over time.

**E1.** What's the roll-up cadence and trigger?

   a. **Weekly:** Auto-generated every Friday/Sunday? Or on-demand?
   b. **Monthly:** Aligned to calendar months or your business reporting cycle?
   c. **Quarterly:** Aligned to fiscal quarters?

**E2.** For weekly roll-ups, what's the format? A narrative summary? A structured template with sections? A combination? Draft a rough outline of what a "perfect weekly summary" would look like for you.

**E3.** For the quarterly achievement portfolio: what's the audience? Is this for your own reference, for sharing with your manager, for board-level reporting, or for self-advocacy in compensation discussions? Audience shapes framing.

**E4.** How should roll-ups handle contradictions or evolution? (e.g., a decision made in Week 1 was reversed in Week 3.) Should the quarterly view show the final state, the full arc, or both?

**E5.** For per-person profiles: how often should these be refreshed? Continuously updated with each daily summary, or rebuilt periodically from accumulated dailies?

**E6.** Do you want the system to proactively surface patterns and anomalies in roll-ups? (e.g., "You've spent 40% more time on Account X this month than last month" or "No 1:1s recorded with [person] in 3 weeks.") This is high-value but requires more sophisticated analysis.

---

## F. Query & Retrieval

These questions define how you interact with accumulated intelligence beyond scheduled outputs.

**F1.** What kinds of ad-hoc queries do you anticipate asking most often? Rank these by likely frequency:

   a. "What's the history of [decision/topic]?"
   b. "Summarize my interactions with [person] over [time period]"
   c. "What did I commit to this week that I haven't completed?"
   d. "What's happened on [project/account] since [date]?"
   e. "What are the top themes across my last N days?"
   f. Something else entirely?

**F2.** What's the query interface? Options:

   a. Chat with Claude (paste context or have it pull from storage)
   b. A dedicated Streamlit/web UI
   c. Slack bot (ask questions in Slack, get answers)
   d. Obsidian search (if stored there)
   e. CLI tool

**F3.** How fast does query response need to be? Seconds (requires pre-indexed data) or is a 30-60 second processing delay acceptable?

**F4.** Do you need to share query results with others, or is this strictly personal retrieval?

---

## G. Infrastructure & Operations

These questions address the practical engineering and cost considerations.

**G1.** Where does this system run? Options:

   a. Local machine (simple but not reliable for scheduled jobs)
   b. Cloud VM / container (AWS, GCP, Railway, Render)
   c. Serverless functions (Lambda, Cloud Functions)
   d. A managed orchestration platform (n8n cloud, Temporal cloud)

**G2.** What's your budget for ongoing operation? Consider:

   a. LLM API costs (estimate: $2-10/day depending on volume and model tier)
   b. Cloud hosting ($10-50/month for a basic setup)
   c. Third-party API costs (most sources are free at your volume, but check)
   d. Storage (minimal unless retaining raw transcripts long-term)

**G3.** What's your build vs. buy tolerance? Are you willing to wire this together yourself (Python + APIs + Claude), or do you want a platform that handles orchestration (n8n, Zapier, custom agents)?

**G4.** Monitoring and reliability: if the daily synthesis fails to run, how do you know? Do you need alerting, or is "check it when you notice it's missing" sufficient for v1?

**G5.** Who maintains this system? You personally, or does it need to be robust enough that someone else could operate it? This significantly affects how much you invest in documentation, error handling, and modularity.

**G6.** What's the testing strategy? How do you validate that the system is producing accurate, useful summaries? Manual review of every daily for the first N weeks? Spot checks? A formal eval framework?

---

## H. Security, Privacy & Compliance

These questions are especially important given the personnel evaluation use case and the eventual deployment against Bounce.AI data.

**H1.** Does Bounce.AI have data governance policies that constrain where employee communication data can be processed or stored? Check with legal/IT before building against work data.

**H2.** If using Claude API to process Slack messages and meeting transcripts that mention employees by name, are you comfortable with that data passing through Anthropic's API? (Note: Anthropic's data retention policies for API usage differ from the consumer product.)

**H3.** Do you need audit logging? (i.e., a record of what data was ingested, when, and what summaries were produced.) This matters for compliance and for debugging.

**H4.** Should the system support data deletion requests? (e.g., if an employee leaves and you need to purge their data from the system.)

**H5.** Is there a distinction between data you can process in a personal capacity vs. data that belongs to Bounce.AI? Where's that boundary?

**H6.** If the system stores per-person performance evidence, where does that live relative to official HR systems? Is it a personal reference, or does it feed into formal processes?

---

## I. Success Criteria & Iteration

**I1.** What does "working well" look like after 30 days of operation? Be specific. (e.g., "I open my daily summary each morning and find it accurate and useful 4 out of 5 days.")

**I2.** What would make you abandon this project? What's the failure mode you're most worried about?

**I3.** What's the first output you'd want to produce from this system that you can't produce today? (This is your North Star for v1.)

**I4.** How will you measure whether the system is actually saving you time vs. creating a new thing to manage?

**I5.** What's the iteration cadence? Weekly tweaks to prompts and filters? Or build it, let it run, and revisit monthly?

---

*Work through these roughly in section order. Sections A and B unlock everything else. Don't over-deliberate — some answers will only become clear once you start building.*
