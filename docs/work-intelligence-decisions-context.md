# Work Intelligence System: Conversation Context & Decisions Log

**Source conversation:** Claude.ai, March 23, 2026
**Purpose:** Preserves architectural decisions and context from the initial planning session that aren't fully reflected in the two companion documents.

---

## Companion Documents

1. **work-intelligence-system-plan.md** — Conceptual framing, question framework, data source mapping, architecture overview, implementation roadmap, and open questions.
2. **work-intelligence-architecture-questions.md** — Structured question guide (9 sections, ~50 questions) to drive architecture decisions. Intended to be worked through in Claude Code planning mode.

---

## Decisions Made

### Architecture Stack
**Decided:** Python + Claude Code + Cowork scheduling, running against Claude plan limits (not API keys).

**Rationale:** Cowork handles the scheduled trigger. Claude Code executes the pipeline (API ingestion, normalization, LLM synthesis, file output) against plan allocation. This avoids API costs entirely and keeps the system within the Claude ecosystem. Python is the implementation language for the pipeline logic.

**What this replaces:** The planning doc still lists n8n, Temporal, custom Python with cron, and serverless as open options. Those are now fallback paths, not primary.

### Cost Strategy
**Decided:** Run on Claude Pro/Max plan limits rather than paying for API usage.

**Rationale:** The system's value needs to be validated before committing to ongoing API spend. Plan-based execution is effectively free. If the system proves out and needs to run fully unattended, graduating to API is straightforward.

**Implication:** The pipeline cannot be fully headless in v1. Cowork triggers it, but it runs within the Claude Code / plan context rather than as an independent service.

### Personnel Evaluation Framing
**Decided:** The system surfaces **evidence and organized observations**, not evaluations or judgments.

**Rationale:** Automated performance assessment from communication data creates legal exposure, fairness problems (verbose communicators get more "evidence"), and context collapse risks (tone/intent misread). The system should produce timestamped contributions, quotes, collaboration records, and coaching moments. The human makes the judgment call.

**This is a design constraint, not just a preference.** It should be enforced in prompt design — the system should never output language like "performed well" or "underperformed." It presents what happened; you interpret it.

---

## Validation Step (Pre-Build)

### Cowork → Claude Code Spike
**Before building the actual pipeline**, validate the orchestration chain:

1. Set up a Cowork scheduled task that triggers a Claude Code project
2. The Claude Code task should do something simple but representative: pull data from one API (e.g., Gmail), process it with Claude, write a structured output file
3. Run this daily for one week
4. Evaluate: Did it trigger reliably? Did it complete without intervention? Were there auth/timeout/rate-limit issues?

**If the spike succeeds:** proceed with the full pipeline on this architecture.
**If it's flaky:** fall back to a small cloud instance (VM or container) with cron, using API keys. The pipeline code itself doesn't change — only the trigger and execution context.

### Manual Proof of Concept (Phase 0 from Planning Doc)
Also still recommended: spend 3-5 days manually creating the daily summary yourself using Claude to process raw exports (copy-paste transcripts, Slack exports, etc.). This reveals which data sources are highest-signal and which of the 10 daily questions are hardest to answer well. Do this before or in parallel with the Cowork spike.

---

## Key Design Principles Established

1. **Signal over volume.** The hard problem is filtering, not ingestion. The system needs aggressive noise reduction or it produces summaries that are 80% filler.

2. **Temporal composability is the real value.** Daily summaries are useful but perishable. The system becomes transformative when days roll up into weeks, months, and quarters — and when you can query across time.

3. **Calendar is a required data source.** Not in the original concept but identified as essential. It's the skeleton that maps meetings to transcripts and enables time-allocation analysis.

4. **Source linking builds trust.** Summaries should trace back to the specific Slack thread, transcript, or email that generated them. Without provenance, you can't trust or verify the output.

5. **Start with one source, prove value, then expand.** Meeting transcripts from Gmail are the likely Phase 1 MVP source (highest signal-to-noise). Don't try to ingest everything on day one.

---

## Open Questions Carried Forward

These were raised but not resolved. Work through them via the architecture questions doc.

1. **Scope boundary:** Personal tool vs. team-facing? Bounce-only vs. multi-context?
2. **Storage destination:** Obsidian vault, database, hybrid? Needs to support both human-readable output and structured queries.
3. **Confidentiality boundaries:** Which channels/categories of communication are excluded from processing? HR, legal, board-level?
4. **Bounce data governance:** Check with legal/IT whether employee communication data can be processed through external LLM APIs (even on a plan, data passes through Anthropic's infrastructure).
5. **Real-time vs. batch:** Is end-of-day synthesis sufficient, or do you need intraday updates?
6. **Success criteria:** What does "working well" look like after 30 days? Define before building.

---

*Import all three documents into the work account project. Use the architecture questions doc to drive Claude Code planning mode. Refer back to this doc for decisions already made and constraints already established.*
