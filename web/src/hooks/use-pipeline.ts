"use client";

import { useCallback, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { API_BASE } from "@/lib/api";
import { usePipelineStore, type PipelineEvent } from "@/stores/pipeline-store";
import { useUIStore } from "@/stores/ui-store";

export function usePipelineRun() {
  const store = usePipelineStore();
  const queryClient = useQueryClient();
  const setSelectedDate = useUIStore((s) => s.setSelectedDate);
  const setSelectedViewType = useUIStore((s) => s.setSelectedViewType);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Clean up EventSource on unmount
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    };
  }, []);

  const connectSSE = useCallback(
    (runId: string, targetDate: string) => {
      // Close any existing connection
      eventSourceRef.current?.close();

      const es = new EventSource(`${API_BASE}/runs/${runId}/stream`);
      eventSourceRef.current = es;

      es.onmessage = (event) => {
        try {
          const data: PipelineEvent = JSON.parse(event.data);
          store.updateFromEvent(data);

          if (data.status === "complete") {
            es.close();
            eventSourceRef.current = null;

            // Invalidate summary queries so new data appears
            void queryClient.invalidateQueries({ queryKey: ["summaries"] });
            void queryClient.invalidateQueries({
              queryKey: ["summary", targetDate],
            });

            toast.success(`Pipeline complete for ${targetDate}`, {
              action: {
                label: "View Summary",
                onClick: () => {
                  setSelectedDate(targetDate);
                  setSelectedViewType("daily");
                },
              },
            });

            // Auto-reset to idle after 3 seconds
            setTimeout(() => {
              usePipelineStore.getState().reset();
            }, 3000);
          }

          if (data.status === "failed") {
            es.close();
            eventSourceRef.current = null;
            toast.error(data.error ?? "Pipeline run failed");
          }
        } catch {
          // Ignore malformed messages
        }
      };

      es.onerror = () => {
        // EventSource auto-reconnects on transient errors.
        // If permanently closed (readyState === CLOSED), mark as error.
        if (es.readyState === EventSource.CLOSED) {
          eventSourceRef.current = null;
          const currentStatus = usePipelineStore.getState().status;
          if (currentStatus === "running") {
            usePipelineStore.getState().updateFromEvent({
              run_id: runId,
              status: "failed",
              stage: null,
              stages: usePipelineStore.getState().stages,
              target_date: targetDate,
              elapsed_s: usePipelineStore.getState().elapsedS,
              error: "Lost connection to pipeline",
            });
            toast.error("Lost connection to pipeline");
          }
        }
      };
    },
    [store, queryClient, setSelectedDate, setSelectedViewType],
  );

  const triggerRun = useCallback(
    async (targetDate?: string) => {
      const date =
        targetDate ??
        new Date(Date.now() - 86400000).toISOString().slice(0, 10);

      try {
        const res = await fetch(`${API_BASE}/runs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target_date: date }),
        });

        if (res.status === 409) {
          toast.warning("A pipeline run is already in progress");
          return;
        }

        if (!res.ok) {
          const err = await res
            .json()
            .catch(() => ({ detail: `HTTP ${res.status}` }));
          toast.error(err.detail ?? "Failed to start pipeline");
          return;
        }

        const data = (await res.json()) as { run_id: string };
        store.startRun(data.run_id, date);
        connectSSE(data.run_id, date);
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Failed to start pipeline",
        );
      }
    },
    [store, connectSSE],
  );

  return {
    triggerRun,
    isRunning: store.status === "running",
  };
}

export interface RunResponse {
  id: string;
  target_date: string;
  status: "running" | "complete" | "failed";
  stages: Array<{
    name: string;
    status: "pending" | "running" | "complete" | "failed";
    elapsed_s: number | null;
  }>;
  started_at: string;
  completed_at: string | null;
  duration_s: number | null;
  error_message: string | null;
  error_stage: string | null;
}

export function useRunHistory() {
  return useQuery<RunResponse[]>({
    queryKey: ["pipeline-runs"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/runs?limit=14`);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json() as Promise<RunResponse[]>;
    },
    refetchInterval: 30_000,
  });
}
