# Features Research: Work Intelligence / Daily Synthesis

**Research date:** 2026-03-23
**Researcher:** Claude (agent-assisted)
**Dimension:** Features
**Project:** Work Intelligence System (Daily Summarizer)

---

## Scope

This document catalogs features across the work intelligence / daily synthesis product space, organized by the six dimensions requested: data ingestion, synthesis/summarization, temporal roll-ups, source attribution, output formats, and feedback/learning loops. Each feature is classified as table stakes, differentiator, or anti-feature, with complexity estimates and dependency notes.

**Competitive reference set:** Reclaim.ai, Mem.ai, Reflect, Notion AI, Granola, Otter.ai, Fireflies.ai, Read.ai, Fellow.app, and custom LLM pipelines processing calendar + transcript data.

---

## 1. Data Ingestion

### Table Stakes (Must-Have or Users Leave)

| Feature | Description | Complexity | Dependencies | Notes |
|---------|-------------|------------|--------------|-------|
| **Calendar event ingestion** | Pull meeting titles, times, attendees, descriptions from Google Calendar | Low | Google Calendar API auth | The skeleton everything hangs on. Without it, system cannot correlate transcripts to meetings or assess time allocation. |
| **Meeting transcript ingestion** | Ingest transcripts from at least one source (Gemini, Gong, Otter, Fireflies) | Medium | Source-specific parsing; email or API access | The primary content source. Every competitor in this space ingests transcripts. Format varies wildly (email attachment, API, webhook). |
| **Deduplication** | Detect and merge duplicate events/transcripts from overlapping sources | Medium | Depends on having 2+ sources | Without this, summaries repeat themselves. Calendar event + transcript + email confirmation for same meeting = one logical event. |
| **Noise filtering** | Exclude low-signal content: automated notifications, scheduling emails, empty calendar holds | Low-Medium | Heuristic rules or classifier | 80%+ of raw data is noise. System is useless without aggressive filtering. Reclaim.ai and Notion AI both learned this the hard way. |

### Differentiators (Competitive Advantage)

| Feature | Description | Complexity | Dependencies | Notes |
|---------|-------------|------------|--------------|-------|
| **Slack ingestion with channel prioritization** | Ingest Slack messages with configurable priority per channel (e.g., #leadership = high, #random = skip) | High | Slack API, channel taxonomy | Highest volume source. Mem.ai ingests broadly; the differentiation is in *selective* ingestion. Out of scope for v1 per PROJECT.md. |
| **Cross-source event correlation** | Automatically link a calendar event to its transcript, related Slack thread, and follow-up email into a single "meeting record" | High | Calendar + transcript + Slack ingestion | This is what separates a synthesis tool from a search tool. Few products do this well. Fellow.app attempts it for meeting workflows. |
| **Incremental ingestion** | Process only new/changed data since last run, not full re-scan | Medium | State tracking, cursor/token management | Critical for cost control when running on plan limits rather than API. Enables daily batch to run in minutes, not hours. |
| **Configurable confidentiality boundaries** | Exclude specific calendar categories, channels, or senders from processing (HR, legal, board) | Medium | Ingestion layer filtering | PROJECT.md flags this as TBD. No competitor handles this well. Most are all-or-nothing. |

### Anti-Features (Deliberately NOT Build)

| Feature | Why Not | Risk if Built |
|---------|---------|---------------|
| **Real-time streaming ingestion** | End-of-day batch is sufficient for v1 (per PROJECT.md). Real-time adds massive complexity for marginal daily-summary value. | Over-engineering; cost explosion; distraction from synthesis quality. |
| **Automatic Slack DM ingestion** | DMs contain the most sensitive content. Blanket ingestion creates privacy and trust problems. | Legal exposure, employee trust erosion, potential policy violations. |
| **Browser history / screen time tracking** | Invasive; low signal-to-synthesis ratio; RescueTime already exists. | Privacy overreach; data volume explosion with minimal synthesis value. |

---

## 2. Synthesis / Summarization

### Table Stakes

| Feature | Description | Complexity | Dependencies | Notes |
|---------|-------------|------------|--------------|-------|
| **Structured daily summary** | Produce a daily summary organized by consistent categories (not freeform prose) | Medium | Ingested data, LLM access, prompt engineering | Every competitor produces some form of daily output. Structure is what makes it scannable in 5 minutes. The 10-question framework in the planning doc is the structure. |
| **Evidence-only framing** | Surface what happened (quotes, timestamps, contributions) without evaluative language | Medium | Prompt engineering, output validation | PROJECT.md mandates this. No "performed well" or "underperformed." This is both an ethical requirement and a legal safeguard. |
| **Per-meeting synthesis** | Summarize each meeting individually before rolling into daily view | Medium | Transcript ingestion, meeting boundary detection | Users need to drill into specific meetings. Granola, Otter.ai, and Fireflies all produce per-meeting summaries as baseline. |
| **Decision extraction** | Identify and extract decisions made, by whom, with stated rationale | Medium-High | NLP/LLM with good prompt design | Core question #3 from the framework. Most meeting note tools (Fellow, Fireflies) attempt this. Quality varies enormously. |
| **Task/commitment extraction** | Identify action items, who owns them, and deadlines | Medium | Similar to decision extraction | Core question #7. Otter.ai, Fireflies, Fellow, and Read.ai all extract action items. Table stakes for meeting intelligence. |

### Differentiators

| Feature | Description | Complexity | Dependencies | Notes |
|---------|-------------|------------|--------------|-------|
| **Cross-meeting synthesis** | Connect threads across multiple meetings in the same day (e.g., "the pricing discussion in the 10am continued in the 2pm with different stakeholders") | High | All per-meeting summaries, entity resolution | This is where daily synthesis surpasses per-meeting tools. No single-meeting product does this. It requires understanding that topics span meetings. |
| **Substance filtering (signal vs. noise)** | Distinguish high-impact events from routine updates using learned user priorities | High | Feedback loop (see section 6), prompt engineering | The planning doc identifies this as the hard problem. "Two people in the same meeting would highlight different things as substantive." |
| **Counterfactual awareness** | Flag what did NOT happen: cancelled meetings, missing follow-ups, silence from usually-active people | High | Historical baseline, pattern detection | Mentioned in the planning doc as a novel intelligence layer. Absence of signal is itself a signal. No competitor does this. |
| **Theme extraction across days** | Identify recurring topics, unresolved questions, and intellectual threads that persist across multiple days | High | Multi-day state, entity/topic tracking | Question #5 from the framework. This is where temporal composability starts to emerge. Mem.ai attempts something like this with their knowledge graph. |
| **Personnel evidence collection** | Maintain per-person running logs of contributions, key quotes, collaboration moments (never evaluative) | High | Entity resolution for people, strict output guardrails | Highest-value and highest-risk feature per the planning doc. Frame as evidence collection, not evaluation. No competitor offers this because of the risk. |

### Anti-Features

| Feature | Why Not | Risk if Built |
|---------|---------|---------------|
| **Automated performance ratings** | System should never render judgments about people. Human makes evaluation calls. | Legal liability, bias amplification, context collapse, trust destruction. |
| **Sentiment analysis on communications** | Crude positive/negative scoring of messages decontextualizes tone. Sarcasm, cultural norms, and relationship context make this unreliable. | False signals presented as data; managers acting on misleading "sentiment scores." |
| **Auto-generated meeting agendas** | Scope creep into meeting management. Fellow.app and Notion AI own this. Focus on post-hoc synthesis, not pre-meeting prep. | Feature sprawl; moves system from intelligence to workflow tool. |
| **Smart replies / auto-drafting** | Generating responses based on synthesis. Different product category entirely. | Liability; voice/tone mismatch; user trust issues. |

---

## 3. Temporal Roll-Ups

### Table Stakes

| Feature | Description | Complexity | Dependencies | Notes |
|---------|-------------|------------|--------------|-------|
| **Weekly summary from dailies** | Aggregate 5 daily summaries into a week-in-review: top accomplishments, open threads, key decisions | Medium | 5 days of structured daily output, LLM processing | The planning doc specifies this. Use case: Monday planning, 1:1 prep. Without weekly roll-ups the system is just a daily log. |
| **Consistent structure across time horizons** | Weekly, monthly, quarterly summaries use the same category framework (just at different granularity) | Low | Template/prompt design | Users should be able to compare a daily "Decisions" section to a monthly "Decisions" section without learning a new format. |

### Differentiators

| Feature | Description | Complexity | Dependencies | Notes |
|---------|-------------|------------|--------------|-------|
| **Monthly narrative with themes** | Produce a thematic narrative (not just a longer list) identifying progress arcs, emerging risks, and strategic shifts | High | 4 weeks of dailies/weeklies, sophisticated prompt engineering | The planning doc calls for "thematic narrative, progress against goals." This requires understanding trajectory, not just aggregation. |
| **Quarterly achievement portfolio** | Structured document suitable for QBR prep, performance self-reviews, and self-advocacy | High | 3 months of roll-ups, goal/OKR context | The planning doc identifies this as a key use case. The real unlock of temporal composability. "What did I accomplish in Q1?" with sourced evidence. |
| **Per-person temporal roll-ups** | Weekly/monthly view of interactions and contributions per direct report or key stakeholder | High | Personnel evidence collection, multi-week state | Performance review prep. The planning doc calls this the highest-value output. Requires careful guardrails. |
| **Per-project temporal roll-ups** | Track a project's evolution across weeks/months: decisions made, pivots, progress | High | Project entity resolution, multi-week state | Useful for retrospectives and handoffs. Requires identifying which meetings/threads belong to which project. |
| **Trend detection across roll-ups** | Identify patterns: "You've had 3 weeks of increasing meeting load" or "The infrastructure topic keeps resurfacing without resolution" | High | Multiple weeks of structured data, statistical/LLM analysis | This is the "personal operating record" insight the planning doc envisions. Moves from summary to intelligence. |

### Anti-Features

| Feature | Why Not | Risk if Built |
|---------|---------|---------------|
| **Automated goal tracking / OKR scoring** | System lacks context on what "progress" means for ambiguous goals. Human judges goal attainment. | False precision; gaming incentives; context collapse on nuanced goals. |
| **Predictive forecasting** | "Based on current trajectory, you will miss your Q2 target." Insufficient data and context for reliable predictions. | False confidence in predictions; users making bad decisions based on unreliable forecasts. |

---

## 4. Source Attribution

### Table Stakes

| Feature | Description | Complexity | Dependencies | Notes |
|---------|-------------|------------|--------------|-------|
| **Per-item source linking** | Every summary item traces back to the specific transcript, calendar event, or message it came from | Medium | Ingestion metadata preservation, output formatting | PROJECT.md explicitly requires this. Without attribution, summaries are unverifiable claims. Users cannot trust or correct unattributed synthesis. |
| **Timestamp preservation** | All evidence carries original timestamps (not just "today" but "10:32 AM in the product sync") | Low | Metadata from ingestion | Timestamps are essential for sequencing events and resolving conflicts. "Was the decision made before or after the data came in?" |
| **Participant attribution** | Attribute statements, decisions, and commitments to specific people | Medium | Speaker identification in transcripts, attendee lists from calendar | "Sarah decided X" vs. "it was decided" is the difference between a useful log and a vague summary. |

### Differentiators

| Feature | Description | Complexity | Dependencies | Notes |
|---------|-------------|------------|--------------|-------|
| **Direct quote preservation** | Include verbatim quotes for key moments (decisions, commitments, notable statements) | Medium | Transcript access, quote selection logic | Question #6 (Resonance) from the framework. Preserves the human texture. Most summarizers paraphrase everything and lose the voice. |
| **Source confidence scoring** | Indicate confidence level based on source quality (full transcript = high, calendar title only = low, secondhand reference = very low) | Medium-High | Source metadata, confidence heuristic | Helps user calibrate trust. "This decision was extracted from a full transcript" vs. "inferred from a calendar title." |
| **Cross-reference linking** | Link related items across days: "This follows up on the decision from Tuesday's product sync" | High | Multi-day entity resolution, decision/topic tracking | The planning doc envisions tracing decisions back through discussions that shaped them. This is the knowledge graph aspect. |

### Anti-Features

| Feature | Why Not | Risk if Built |
|---------|---------|---------------|
| **Hiding sources behind a "trust the AI" interface** | Attribution is the entire trust mechanism. If users cannot verify, they cannot correct, and the system becomes an unreliable oracle. | Erosion of trust; uncorrectable errors compounding over time. |

---

## 5. Output Formats

### Table Stakes

| Feature | Description | Complexity | Dependencies | Notes |
|---------|-------------|------------|--------------|-------|
| **Structured markdown file per day** | One markdown file per day with consistent sections, stored locally | Low | Synthesis pipeline output | PROJECT.md specifies flat markdown files for v1. Readable in any editor, versionable in git, compatible with Obsidian. |
| **Scannable in under 5 minutes** | Daily output is concise enough to read over morning coffee | Low (design constraint) | Good prompt engineering for brevity | PROJECT.md core value statement: "worth 5 minutes of my time." If it takes 15 minutes to read, the system failed. |
| **Consistent naming and organization** | Files follow a predictable naming scheme (e.g., `YYYY-MM-DD.md`) in a predictable directory structure | Low | Pipeline output configuration | Users should be able to find any day's summary without searching. Temporal organization is essential. |

### Differentiators

| Feature | Description | Complexity | Dependencies | Notes |
|---------|-------------|------------|--------------|-------|
| **Multiple output tiers** | Executive summary (30 seconds), standard summary (5 minutes), full detail (deep dive) at user's choice | Medium | Multi-pass synthesis or progressive disclosure in output format | Lets user choose depth based on day. Light meeting day = skim. Critical day = deep read. No competitor offers this well. |
| **Obsidian-native output** | Files with YAML frontmatter, wikilinks, tags, and backlinks compatible with Obsidian knowledge management | Medium | Obsidian formatting conventions, entity linking | Planning doc mentions Obsidian as a potential destination. Enables the "second brain" integration naturally. |
| **Structured data sidecar** | JSON or YAML alongside markdown containing machine-readable decisions, tasks, people, and topics for downstream querying | Medium | Parallel output generation | Planning doc notes the need for both readability (markdown) and queryability (structured data). Enables Phase 4 query interface. |
| **Email digest option** | Deliver daily summary via email for consumption outside file system | Low-Medium | Email sending capability | Some users prefer push delivery. Reclaim.ai uses email for daily planning summaries. |

### Anti-Features

| Feature | Why Not | Risk if Built |
|---------|---------|---------------|
| **Interactive dashboard / web UI** | Premature for v1. Adds massive frontend complexity before the synthesis quality is proven. | Engineering distraction; maintenance burden; delays validation of core value proposition. |
| **Slack bot delivery** | Posting summaries into Slack mixes private intelligence with team-visible channels. Personal tool first. | Privacy leakage; team-facing implications before system is reliable. |
| **PDF / formatted report generation** | Over-polished output for a personal tool. Markdown is sufficient and more flexible. | Complexity for aesthetics; slows iteration on content quality. |

---

## 6. Feedback / Learning Loops

### Table Stakes

| Feature | Description | Complexity | Dependencies | Notes |
|---------|-------------|------------|--------------|-------|
| **Manual correction capability** | User can edit the generated summary to fix errors, add context, remove irrelevant items | Low | Markdown files are inherently editable | Minimum viable feedback: user fixes the output. System does not need to be perfect if corrections are easy. |
| **Prompt iteration cycle** | Developer (Micah) can modify synthesis prompts based on observed output quality | Low | Access to prompt templates | The POC is explicitly about refining prompts. This is the v1 learning loop: human reviews, adjusts prompts, quality improves. |

### Differentiators

| Feature | Description | Complexity | Dependencies | Notes |
|---------|-------------|------------|--------------|-------|
| **Thumbs up/down on summary items** | Lightweight per-item feedback that accumulates to improve signal detection | Medium | Feedback storage, prompt conditioning on historical feedback | Planning doc Phase 5. "Add a lightweight feedback mechanism that improves synthesis quality over time." |
| **Substance calibration** | System learns user's definition of "substantive" from corrections and feedback over weeks | High | Feedback loop, preference modeling or few-shot example curation | The planning doc identifies this as the critical learning challenge. "The system needs to learn your definition of substance over time." |
| **Correction propagation** | When user corrects a summary item, the correction informs future synthesis (e.g., "stop summarizing standup status updates, I already know those") | High | Feedback storage, retrieval-augmented prompting | Moves beyond per-session prompting to persistent learned preferences. |
| **Quality metrics tracking** | Track summary quality over time: how often does user edit? Which sections get corrected most? | Medium | Edit tracking, basic analytics | Meta-feedback: the system monitors its own performance trajectory. |
| **Explicit priority configuration** | User declares priorities (projects, people, topics) that weight synthesis toward what matters most | Medium | Configuration layer, prompt conditioning | Rather than learning implicitly, let user explicitly say "I care most about the infrastructure migration and the Q2 hiring plan." |

### Anti-Features

| Feature | Why Not | Risk if Built |
|---------|---------|---------------|
| **Fully automated self-improvement** | System autonomously changing its synthesis behavior without user review creates unpredictable drift. | Silent quality degradation; system optimizes for wrong objective; user loses trust. |
| **Fine-tuning a custom model** | Enormous complexity for marginal gains over good prompt engineering + few-shot examples. | Cost, maintenance burden, model lock-in, training data requirements far exceed personal tool scope. |

---

## Feature Dependencies

The following dependency graph shows which features enable or require others:

```
Calendar Ingestion ──────────────────┐
                                     ├──> Cross-Source Event Correlation ──> Cross-Meeting Synthesis
Transcript Ingestion ────────────────┤
                                     ├──> Per-Meeting Synthesis ──> Structured Daily Summary
Noise Filtering ─────────────────────┘                                      │
                                                                            ├──> Weekly Roll-Up ──> Monthly Narrative ──> Quarterly Portfolio
Per-Item Source Linking ──> Participant Attribution ──> Personnel Evidence   │
                                                                            ├──> Theme Extraction ──> Trend Detection
Manual Correction ──> Thumbs Up/Down ──> Substance Calibration              │
                                                                            └──> Structured Data Sidecar ──> Query Interface (Phase 4)
Prompt Iteration ──> Explicit Priority Config ──> Correction Propagation
```

### Critical Path for v1 (POC)

1. Calendar ingestion (skeleton)
2. Transcript ingestion (substance)
3. Noise filtering (usability)
4. Per-meeting synthesis (building block)
5. Structured daily summary answering Questions 2, 3, 7 (Substance, Decisions, Commitments)
6. Per-item source linking (trust)
7. Structured markdown file per day (output)
8. Manual correction + prompt iteration (learning)

---

## Complexity Summary

| Complexity | Count | Examples |
|------------|-------|----------|
| **Low** | 7 | Calendar ingestion, timestamp preservation, consistent naming, manual correction, prompt iteration, scannable output, consistent roll-up structure |
| **Medium** | 14 | Transcript ingestion, deduplication, noise filtering, per-meeting synthesis, weekly roll-up, source linking, participant attribution, incremental ingestion, quote preservation, structured data sidecar, email digest, thumbs up/down, quality metrics, explicit priority config |
| **Medium-High** | 3 | Decision extraction, source confidence scoring, configurable confidentiality boundaries |
| **High** | 10 | Slack ingestion, cross-source correlation, cross-meeting synthesis, substance filtering, counterfactual awareness, theme extraction, monthly narrative, quarterly portfolio, per-person roll-ups, substance calibration, correction propagation |

---

## Competitive Positioning Notes

**What existing tools do well:**
- Otter.ai, Fireflies.ai, Granola: Per-meeting transcription and summarization (action items, decisions). They own the single-meeting workflow.
- Reclaim.ai: Calendar intelligence, time blocking, scheduling optimization. They own calendar-as-operating-system.
- Mem.ai: Knowledge management with AI-powered retrieval and connections across notes. They own the "second brain" search.
- Notion AI: In-context summarization within an existing workspace. They own "AI inside your existing docs."
- Fellow.app: Meeting management lifecycle (agenda, notes, action items, 1:1s). They own the meeting workflow.
- Read.ai: Meeting analytics with engagement metrics. They own meeting performance data.

**The gap this system fills:**
None of these tools synthesize across all meetings in a day into a coherent daily intelligence briefing. They are per-meeting tools, per-workspace tools, or scheduling tools. The white space is the **cross-source, cross-meeting, temporal synthesis layer** that sits on top of individual meeting tools and produces a personal operating record. The planning doc's core insight is correct: the opportunity is a synthesis layer, not another ingestion tool.

**Strongest differentiation opportunities for this project:**
1. Cross-meeting daily synthesis (no one does this)
2. Temporal roll-ups with evidence chains (no one does this well)
3. Personnel evidence collection with strict ethical guardrails (no one attempts this)
4. Counterfactual awareness (entirely novel)
5. Learned substance calibration (Mem.ai is closest but in a different product category)

---

## Research Confidence & Gaps

**High confidence:** Data ingestion features, output format features, and basic synthesis features are well-understood from existing products and the planning documents.

**Medium confidence:** Feedback/learning loop features are less proven in this product category. The planning doc's Phase 5 framing is reasonable but implementation complexity may be underestimated.

**Gaps to investigate:**
- How do existing LLM pipelines handle transcript quality variance (partial transcripts, speaker misidentification, crosstalk)?
- What is the actual token cost per day for processing 3-8 meeting transcripts through Claude? Critical for the "zero incremental cost" constraint.
- How do users of Mem.ai and Reflect actually interact with temporal views? Is weekly roll-up genuinely used, or do people just search?

---

*Research completed: 2026-03-23. Feeds into requirements definition and architecture decisions for Work Intelligence System.*
