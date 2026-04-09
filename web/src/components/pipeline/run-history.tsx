"use client";

import { useState } from "react";
import { format, parseISO } from "date-fns";
import { formatDistanceToNow } from "date-fns";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { useRunHistory, type RunResponse } from "@/hooks/use-pipeline";
import { useUIStore } from "@/stores/ui-store";

export function RunHistory() {
  const { data: runs, isLoading, error } = useRunHistory();

  if (isLoading) {
    return (
      <div className="space-y-2 px-3 py-2">
        <Skeleton className="h-10 w-full rounded-md" />
        <Skeleton className="h-10 w-full rounded-md" />
        <Skeleton className="h-10 w-full rounded-md" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="px-3 py-4 text-center text-xs text-muted-foreground">
        Failed to load run history
      </div>
    );
  }

  if (!runs || runs.length === 0) {
    return (
      <div className="px-3 py-4 text-center text-xs text-muted-foreground">
        No pipeline runs yet
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-0.5 px-2">
      {runs.map((run) => (
        <RunRow key={run.id} run={run} />
      ))}
    </div>
  );
}

function RunRow({ run }: { run: RunResponse }) {
  const [expanded, setExpanded] = useState(false);
  const setSelectedDate = useUIStore((s) => s.setSelectedDate);
  const setActiveTab = useUIStore((s) => s.setActiveTab);

  const handleClick = () => {
    if (run.status === "complete") {
      setSelectedDate(run.target_date);
      setActiveTab("summaries");
    } else if (run.status === "failed") {
      setExpanded((prev) => !prev);
    }
  };

  const dateLabel = (() => {
    try {
      return format(parseISO(run.target_date), "MMM d");
    } catch {
      return run.target_date;
    }
  })();

  const durationLabel =
    run.duration_s != null ? `${run.duration_s.toFixed(1)}s` : "--";

  const timeAgo = (() => {
    try {
      return formatDistanceToNow(parseISO(run.started_at), {
        addSuffix: true,
      });
    } catch {
      return "";
    }
  })();

  return (
    <div>
      <button
        onClick={handleClick}
        data-kb-item
        className={cn(
          "flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-xs transition-colors",
          run.status === "running"
            ? "cursor-default"
            : "hover:bg-accent/50 cursor-pointer",
          expanded && "bg-accent/30",
        )}
      >
        <span className="w-12 shrink-0 font-medium">{dateLabel}</span>
        <StatusBadge status={run.status} />
        <span className="ml-auto shrink-0 tabular-nums text-muted-foreground">
          {durationLabel}
        </span>
        <span className="shrink-0 text-muted-foreground/70 w-20 text-right truncate">
          {timeAgo}
        </span>
      </button>

      {expanded && run.status === "failed" && (
        <div className="mx-2 mb-1 rounded-md bg-destructive/10 p-3">
          {run.error_stage && (
            <p className="text-xs font-medium text-destructive mb-1">
              Failed at: {run.error_stage}
            </p>
          )}
          {run.error_message && (
            <pre className="font-mono text-xs text-destructive/80 max-h-32 overflow-auto whitespace-pre-wrap break-words">
              {run.error_message}
            </pre>
          )}
          {!run.error_stage && !run.error_message && (
            <p className="text-xs text-muted-foreground">
              No error details available
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: RunResponse["status"] }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none",
        status === "complete" && "bg-green-500/15 text-green-600",
        status === "failed" && "bg-destructive/15 text-destructive",
        status === "running" && "bg-yellow-500/15 text-yellow-600 animate-pulse",
      )}
    >
      {status === "complete" && "Success"}
      {status === "failed" && "Failed"}
      {status === "running" && "Running"}
    </span>
  );
}
