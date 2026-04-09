"use client";

import { useState } from "react";
import { format, subDays } from "date-fns";
import { Play, Loader2, XCircle, Check } from "lucide-react";
import { usePipelineRun } from "@/hooks/use-pipeline";
import { usePipelineStore } from "@/stores/pipeline-store";

export function RunTrigger() {
  const { triggerRun, isRunning } = usePipelineRun();
  const status = usePipelineStore((s) => s.status);
  const error = usePipelineStore((s) => s.error);
  const errorDismissed = usePipelineStore((s) => s.errorDismissed);
  const dismissError = usePipelineStore((s) => s.dismissError);

  const yesterday = subDays(new Date(), 1);
  const [targetDate, setTargetDate] = useState(
    format(yesterday, "yyyy-MM-dd"),
  );

  const [showDateInput, setShowDateInput] = useState(false);

  const handleTrigger = () => {
    void triggerRun(targetDate);
  };

  // Failed state with error
  if (status === "failed" && !errorDismissed) {
    return (
      <button
        onClick={dismissError}
        className="flex items-center gap-1.5 rounded-md bg-destructive/10 px-2.5 py-1 text-xs text-destructive hover:bg-destructive/20 transition-colors"
        title={error ?? "Pipeline failed"}
      >
        <XCircle className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate max-w-[200px]">
          {error ?? "Pipeline failed"}
        </span>
      </button>
    );
  }

  // Complete state (brief green indicator before auto-reset)
  if (status === "complete") {
    return (
      <div className="flex items-center gap-1.5 rounded-md bg-green-500/10 px-2.5 py-1 text-xs text-green-600">
        <Check className="h-3.5 w-3.5" />
        <span>Complete</span>
      </div>
    );
  }

  // Running state
  if (isRunning) {
    return (
      <div className="flex items-center gap-1.5 rounded-md bg-muted px-2.5 py-1 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        <span>Running...</span>
      </div>
    );
  }

  // Idle state - trigger button
  return (
    <div className="flex items-center gap-1.5">
      <button
        onClick={handleTrigger}
        disabled={isRunning}
        className="flex items-center gap-1.5 rounded-md bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary hover:bg-primary/20 transition-colors disabled:opacity-50"
      >
        <Play className="h-3.5 w-3.5" />
        <span>Run Pipeline</span>
      </button>

      {showDateInput ? (
        <input
          type="date"
          value={targetDate}
          onChange={(e) => {
            setTargetDate(e.target.value);
            setShowDateInput(false);
          }}
          onBlur={() => setShowDateInput(false)}
          className="h-6 rounded border bg-background px-1.5 text-xs"
          autoFocus
        />
      ) : (
        <button
          onClick={() => setShowDateInput(true)}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          title="Change target date"
        >
          {format(new Date(targetDate + "T12:00:00"), "MMM d")}
        </button>
      )}
    </div>
  );
}
