import { create } from "zustand";

export interface PipelineStage {
  name: string;
  status: "pending" | "running" | "complete" | "failed";
  elapsed_s: number | null;
}

export interface PipelineEvent {
  run_id: string;
  status: "running" | "complete" | "failed";
  stage: string | null;
  stages: PipelineStage[];
  target_date: string;
  elapsed_s: number;
  error: string | null;
}

interface PipelineState {
  runId: string | null;
  status: "idle" | "running" | "complete" | "failed";
  targetDate: string | null;
  stages: PipelineStage[];
  elapsedS: number;
  error: string | null;
  errorDismissed: boolean;

  startRun: (runId: string, targetDate: string) => void;
  updateFromEvent: (event: PipelineEvent) => void;
  reset: () => void;
  dismissError: () => void;
}

export const usePipelineStore = create<PipelineState>()((set) => ({
  runId: null,
  status: "idle",
  targetDate: null,
  stages: [],
  elapsedS: 0,
  error: null,
  errorDismissed: false,

  startRun: (runId: string, targetDate: string) =>
    set({
      runId,
      targetDate,
      status: "running",
      stages: [],
      elapsedS: 0,
      error: null,
      errorDismissed: false,
    }),

  updateFromEvent: (event: PipelineEvent) =>
    set({
      status: event.status === "complete" || event.status === "failed"
        ? event.status
        : "running",
      stages: event.stages,
      elapsedS: event.elapsed_s,
      error: event.error,
    }),

  reset: () =>
    set({
      runId: null,
      status: "idle",
      targetDate: null,
      stages: [],
      elapsedS: 0,
      error: null,
      errorDismissed: false,
    }),

  dismissError: () => set({ errorDismissed: true }),
}));
