# Work Intelligence System: Planning & Architecture Document

**Author:** Micah Boster
**Status:** Early Concept / Planning
**Date:** March 22, 2026

---

## TL;DR

Build an automated system that ingests data from Gmail (including call transcripts), HubSpot, Notion, Google Drive, and Slack to produce structured daily summaries and roll them up into longer-horizon intelligence — accomplishments, decision logs, personnel evaluations, and thematic narratives. The core thesis: you already generate the data; you just need the synthesis layer.

---

## 1. The Core Idea — Evaluated

### What's Strong

The fundamental observation is correct and high-leverage. Most knowledge workers generate 90%+ of their professional activity in digital channels, but almost nobody systematically harvests that exhaust into structured self-knowledge. The opportunity is a **personal operating record** — not a journal you write, but one that writes itself from your actual behavior.

The six questions you identified are a solid starting taxonomy. They span task management, substance, decision-making, interpersonal dynamics, intellectual themes, and resonance. That's a well-rounded frame that covers both the *operational* (what happened, what needs to happen) and the *reflective* (how did I lead, what mattered).

### Where It Gets Interesting

The real unlock isn't the daily summary — it's the **temporal composability**. A single day's summary is useful but perishable. The system becomes transformative when:

1. You can ask "What did I accomplish in Q1?" and get a sourced, evidence-backed answer
2. Performance review season arrives and you have a running log of each direct report's contributions, friction points, growth moments, and key quotes — with timestamps and sources
3. You can trace a decision back through the discussions that shaped it, across Slack threads, meeting transcripts, and email chains
4. You notice patterns in your own behavior — when you're most decisive, which topics drain energy, where you add the most value

### Honest Critiques

**Signal-to-noise is the hard problem.** Your Gmail, Slack, and meeting transcripts contain enormous amounts of low-signal content — scheduling back-and-forth, pleasantries, routine updates. The system needs aggressive filtering or it produces summaries that are 80% filler. This is the engineering challenge that will make or break the tool.

**"What happened of substance" requires judgment.** Two people in the same meeting would highlight different things as substantive. The system needs to learn *your* definition of substance over time, which means either explicit training/feedback loops or very good prompt engineering that encodes your priorities.

**Privacy and data sensitivity are non-trivial.** You're aggregating data across systems that may contain confidential client information, HR-sensitive conversations, legal discussions, and personal communications. The system needs clear boundaries about what it ingests, stores, and surfaces. This is especially acute if you're building it to eventually run against Bounce.AI work data.

**The "personnel evaluation" use case needs careful design.** This is arguably the highest-value output but also the most dangerous if done poorly. An AI summarizing a direct report's performance from Slack messages and meeting transcripts could easily produce biased or decontextualized assessments. It should surface evidence and quotes, not render judgments.

---

## 2. Refined Question Framework

Your original six questions are good. Here's a restructured and expanded version:

### Daily Synthesis Questions

| # | Category | Core Question | Why It Matters |
|---|----------|--------------|----------------|
| 1 | **Task Management** | What needs to go on or come off a todo list? | Captures commitments made, deadlines set, items completed or deferred |
| 2 | **Substance** | What happened today that moved the needle? | Filters noise; identifies high-impact events, conversations, and outputs |
| 3 | **Decisions** | What decisions were made, by whom, and with what rationale? | Builds a decision log; critical for accountability and retrospectives |
| 4 | **People & Team** | How did I interact with my team? How did they perform? | Captures leadership moments, coaching opportunities, collaboration quality |
| 5 | **Themes & Questions** | What important themes or unresolved questions surfaced? | Tracks intellectual threads that persist across days and weeks |
| 6 | **Resonance** | Were there quotes, comments, or moments of specific resonance? | Preserves the human texture — the things that stick with you |
| 7 | **Commitments & Follow-ups** | What did I promise to others? What was promised to me? | Distinct from tasks — these are social contracts that affect trust |
| 8 | **Risks & Flags** | What should I be worried about? What felt off? | Early warning system for problems before they become crises |
| 9 | **External Signals** | What came in from outside my team — clients, partners, leadership — that matters? | Ensures external context doesn't get buried in internal noise |
| 10 | **Energy & Focus** | Where did I spend my time? Was that the right allocation? | Time-use audit; identifies drift between priorities and actual behavior |

### Roll-Up Intelligence (Weekly / Monthly / Quarterly)

| Horizon | Output | Use Case |
|---------|--------|----------|
| **Weekly** | Week-in-review summary with top accomplishments, open threads, team pulse | Monday planning, 1:1 prep |
| **Monthly** | Thematic narrative, progress against goals, personnel development notes | Leadership self-assessment, manager reporting |
| **Quarterly** | Achievement portfolio, decision log review, team evaluation drafts, goal reconciliation | QBR prep, performance reviews, self-advocacy docs |
| **Ad-hoc** | Query-driven retrieval: "What's the history of decision X?" or "Show me all interactions with [person] this quarter" | Real-time research and context retrieval |

---

## 3. Data Sources — Mapping & Considerations

### Source Inventory

| Source | What It Contains | Ingestion Notes |
|--------|-----------------|-----------------|
| **Gmail** | Call transcripts (Gong/Fireflies/etc.), email threads, scheduling, external comms | Transcripts are gold. Email threads need aggressive deduplication. Filter out newsletters, automated notifications, etc. |
| **Slack** | Real-time team communication, decisions made informally, cultural signals | Highest volume, lowest average signal. Channel prioritization is critical. DMs may contain the most sensitive and substantive content. |
| **HubSpot** | Client interactions, deal progression, account activity | Structured data — easier to ingest. Focus on activity logs, deal stage changes, notes, and meeting outcomes. |
| **Notion** | Documentation, meeting notes, project plans, wikis | May overlap with other sources. Useful for capturing structured work product and institutional knowledge. |
| **Google Drive** | Documents, spreadsheets, presentations created or edited | Signals what you *produced* vs. what you discussed. Edit timestamps tell a story about where time went. |
| **Calendar** | Meeting schedule, attendee lists, time allocation | Essential for the "energy & focus" question. Not listed in your original set but probably should be source #6. |

### Missing Sources to Consider

**Calendar (Google Calendar)** is conspicuously absent from your list. It's the skeleton that everything else hangs on — who you met with, for how long, and what the stated purpose was. Without it, the system can't easily map transcripts to meetings or assess time allocation.

**Snowflake / BI tools** — if you're tracking operational metrics at Bounce, the system could correlate your activities with outcomes. "On days when I had 4+ client calls, did account health scores change?"

**Personal notes (Obsidian)** — your second brain vault could serve as both an input (your own reflections and annotations) and a destination (where synthesized intelligence lands).

---

## 4. Architecture — High-Level Thinking

### Processing Pipeline (Conceptual)

```
[Data Sources] → [Ingestion & Normalization] → [Daily Synthesis] → [Structured Storage] → [Roll-Up & Query]
```

**Stage 1: Ingestion & Normalization**
Pull data from each source via API. Normalize into a common event format: timestamp, source, participants, content, type (message, email, transcript, document edit, deal update, etc.). Apply initial filtering (drop low-signal content like calendar reminders, automated notifications, etc.).

**Stage 2: Daily Synthesis**
Run the normalized events through an LLM pipeline that answers the 10 daily questions. This is the core prompt engineering challenge. Likely needs source-specific preprocessing — a Slack channel thread needs different handling than a 45-minute meeting transcript.

**Stage 3: Structured Storage**
Store daily summaries in a structured format (probably a combination of markdown for readability and JSON/DB for queryability). Tag entries with people, projects, themes, and decision IDs for cross-referencing.

**Stage 4: Roll-Up & Query**
Scheduled roll-ups (weekly, monthly, quarterly) that aggregate daily summaries. Also support ad-hoc queries: "What have I discussed with [person] about [topic] in the last 30 days?"

### Key Technical Decisions (To Be Made)

| Decision | Options | Considerations |
|----------|---------|---------------|
| **Orchestration** | n8n, custom Python, Claude Code agents, Temporal | You've already evaluated n8n. Complexity vs. flexibility tradeoff. |
| **LLM Provider** | Claude API, OpenAI, mixed | Claude is the obvious choice given your existing workflows. Sonnet for daily processing, Opus for roll-ups and nuanced analysis. |
| **Storage** | Obsidian vault, Notion, Postgres + vector DB, hybrid | Obsidian aligns with your second brain. But structured queries may need a real DB layer. |
| **Scheduling** | Cron, event-driven, hybrid | Daily batch is simplest. Event-driven (process each transcript as it arrives) is more responsive but more complex. |
| **Output Format** | Daily email digest, Slack summary, Obsidian daily note, dashboard | Start with the simplest useful output and iterate. |

---

## 5. The Personnel Evaluation Use Case — Special Attention

This deserves its own section because it's both the highest-value and highest-risk output.

### What Makes It Valuable

Performance reviews are universally dreaded because managers have to reconstruct months of context from memory. If the system maintains a running log per person — what they contributed, how they communicated, what feedback they received, how they responded to challenges — the review practically writes itself. More importantly, it writes itself from *evidence*, not recency bias.

### What Makes It Risky

1. **Context collapse.** A Slack message that reads as dismissive might have been sarcastic banter between friends. The system can't reliably distinguish tone without deep interpersonal context.
2. **Selection bias.** If someone primarily communicates in channels the system doesn't monitor (e.g., in-person conversations, phone calls without transcripts), their contributions will be systematically underrepresented.
3. **Legal exposure.** Depending on jurisdiction, automated monitoring and evaluation of employees raises legal questions. HR and legal should be consulted before deploying this at Bounce.
4. **Fairness.** Verbose communicators will generate more "evidence" than quiet high-performers. The system needs to account for communication style differences.

### Recommended Approach

Frame the personnel output as **"evidence collection and organization"** rather than **"evaluation."** The system surfaces timestamped observations, quotes, and contribution records. You make the judgments. This keeps a human in the loop and avoids the legal and ethical issues of automated assessment.

Structure per-person files as:
1. Key contributions and deliverables (sourced)
2. Communication patterns and collaboration moments
3. Notable quotes and exchanges
4. Areas where coaching was provided or needed
5. Trajectory notes (improvement, plateau, regression)

---

## 6. Implementation Roadmap — Suggested Phases

### Phase 0: Manual Proof of Concept
Before building anything, spend one week manually creating the daily summary yourself using your actual data. This will reveal which sources are most valuable, which questions are hardest to answer, and what the right output format feels like. Use Claude to help process transcripts and Slack exports manually.

### Phase 1: Single-Source MVP
Pick the highest-signal source (probably meeting transcripts from Gmail) and build an automated daily summary from that alone. Get the prompt engineering right for one source before adding complexity.

### Phase 2: Multi-Source Daily Digest
Add Slack and Calendar. Build the normalization layer. Produce a comprehensive daily summary that answers all 10 questions.

### Phase 3: Temporal Roll-Ups
Build the weekly and monthly aggregation layer. Start maintaining per-person and per-project running files.

### Phase 4: Query Interface
Build an ad-hoc query capability: "What decisions have we made about [X]?" or "Summarize my interactions with [person] this month."

### Phase 5: Feedback & Learning
Add a lightweight feedback mechanism (thumbs up/down on summary items, ability to correct or annotate) that improves synthesis quality over time.

---

## 7. Open Questions

1. **Scope boundary:** Is this a personal tool (your data, your summaries) or does it eventually serve a team? The architecture differs significantly.
2. **Data retention policy:** How long do raw inputs persist vs. synthesized summaries? Do you need the raw data after synthesis, or is the summary sufficient?
3. **Real-time vs. batch:** Do you need intraday updates (e.g., before an afternoon meeting, catch up on what happened this morning), or is end-of-day sufficient?
4. **Integration with existing workflows:** Should this feed into your Obsidian vault? Replace your existing meeting notes workflow? Augment your QBR deck generation pipeline?
5. **Cost modeling:** Running every meeting transcript and Slack day through Claude API adds up. What's the acceptable cost per day for this system?
6. **Multi-account / multi-context:** You mentioned moving this to a work account. Does the system need to handle both Nighthawk and Bounce contexts, or is it Bounce-only?
7. **Confidentiality boundaries:** Are there categories of communication (HR, legal, board-level) that should be explicitly excluded from automated processing?

---

## 8. What Else to Look At (Your Question #7)

Beyond the six categories you identified, consider these additional intelligence layers:

**Relationship mapping.** Who are you spending time with, and is that the right distribution? Are there key stakeholders you're underinvesting in? This falls out naturally from calendar + communication data.

**Sentiment and energy tracking.** Not in a crude "positive/negative" way, but tracking which topics and interactions energize vs. drain. Over time, this becomes a powerful signal about role fit and organizational health.

**Knowledge graph construction.** As decisions, people, projects, and themes accumulate, the system can map relationships between them. "This decision about pricing is connected to that client conversation which relates to this competitive threat." This is your Obsidian second brain thesis taken to its logical conclusion.

**Counterfactual awareness.** What *didn't* happen that should have? Meetings that were scheduled but cancelled. Follow-ups that were promised but not delivered. Silence from someone who's usually active. Absence of signal is itself a signal.

**Institutional memory.** When a new team member joins, could this system generate an onboarding briefing? "Here's what this team has been working on, here are the key decisions and their rationale, here are the active threads."

---

*Next steps: Validate the question framework against a real day's data (Phase 0). Identify API access and authentication requirements for each source. Decide on orchestration stack.*
