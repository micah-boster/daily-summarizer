/* ------------------------------------------------------------------ */
/*  TypeScript types matching the FastAPI response models              */
/* ------------------------------------------------------------------ */

// --- Daily summary types ---

export interface SummaryListItem {
  date: string;
  meeting_count: number | null;
  commitment_count: number | null;
  has_sidecar: boolean;
}

export interface SummaryResponse {
  date: string;
  markdown: string;
  sidecar: DailySidecar | null;
}

export interface StatusResponse {
  status: string;
  db_connected: boolean;
  summary_count: number;
  last_summary_date: string | null;
}

// --- Sidecar nested types ---

export interface SidecarTask {
  description: string;
  owner: string | null;
  source_meeting: string;
  date_captured: string;
  due_date: string | null;
  status: string; // "new" | "in-progress" | "completed"
}

export interface SidecarDecision {
  description: string;
  decision_makers: string[];
  rationale: string | null;
  source_meeting: string;
}

export interface SidecarCommitment {
  who: string;
  what: string;
  by_when: string; // ISO date, "week of YYYY-MM-DD", or "unspecified"
  source: string[];
}

export interface SidecarMeeting {
  title: string;
  time: string;
  participants: string[];
  has_transcript: boolean;
}

export interface SidecarEntityReference {
  entity_id: string;
  name: string;
  confidence: number;
}

export interface SidecarEntitySummary {
  entity_id: string;
  name: string;
  entity_type: string;
  mention_count: number;
}

export interface DailySidecar {
  date: string;
  generated_at: string;
  meeting_count: number;
  transcript_count: number;
  tasks: SidecarTask[];
  decisions: SidecarDecision[];
  commitments: SidecarCommitment[];
  source_meetings: SidecarMeeting[];
  substance_entity_refs: SidecarEntityReference[][];
  decision_entity_refs: SidecarEntityReference[][];
  commitment_entity_refs: SidecarEntityReference[][];
  entity_summary: SidecarEntitySummary[];
}

// --- Weekly roll-up types ---

export interface WeeklyRollupListItem {
  week_label: string;
  year: number;
  week_number: number;
  start_date: string | null;
  end_date: string | null;
  daily_count: number;
}

export interface WeeklyRollupResponse {
  week_number: number;
  year: number;
  start_date: string | null;
  end_date: string | null;
  markdown: string;
  sidecar: Record<string, unknown> | null;
}

// --- Monthly roll-up types ---

export interface MonthlyRollupListItem {
  month_label: string;
  year: number;
  month: number;
}

export interface MonthlyRollupResponse {
  month: number;
  year: number;
  markdown: string;
  sidecar: Record<string, unknown> | null;
}

// --- Entity types ---

export interface EntityListItem {
  entity_id: string;
  name: string;
  entity_type: string; // "partner" | "person" | "initiative"
  mention_count: number;
  commitment_count: number;
  last_active_date: string | null;
}

export interface ActivityItemResponse {
  source_type: string; // "substance" | "decision" | "commitment"
  source_date: string;
  context_snippet: string | null;
  confidence: number;
  significance_score: number;
}

export interface ActivityDay {
  date: string;
  items: ActivityItemResponse[];
}

export interface EntityScopedViewResponse {
  entity_name: string;
  entity_type: string;
  entity_id: string;
  from_date: string | null;
  to_date: string | null;
  total_mentions: number;
  aliases: string[];
  open_commitments: ActivityItemResponse[];
  highlights: ActivityItemResponse[];
  activity_by_date: ActivityDay[];
}

export interface RelatedEntityItem {
  entity_id: string;
  name: string;
  entity_type: string;
  co_mention_count: number;
}
