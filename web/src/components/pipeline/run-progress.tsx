"use client";

import { useState } from "react";
import { Check, Loader2, Circle, XCircle, ChevronUp } from "lucide-react";
import { usePipelineStore, type PipelineStage } from "@/stores/pipeline-store";

function formatElapsed(seconds: number | null): string {
  if (seconds === null) return "";
  return `${seconds.toFixed(1)}s`;
}

function StageIcon({ status }: { status: PipelineStage["status"] }) {
  switch (status) {
    case "complete":
      return <Check className="h-3 w-3 text-green-500" />;
    case "running":
      return <Loader2 className="h-3 w-3 animate-spin text-blue-500" />;
    case "failed":
      return <XCircle className="h-3 w-3 text-destructive" />;
    case "pending":
    default:
      return <Circle className="h-3 w-3 text-muted-foreground/50" />;
  }
}

export function RunProgress() {
  const status = usePipelineStore((s) => s.status);
  const stages = usePipelineStore((s) => s.stages);
  const elapsedS = usePipelineStore((s) => s.elapsedS);
  const [expanded, setExpanded] = useState(false);

  if (status !== "running" || stages.length === 0) {
    return null;
  }

  const currentStage = stages.find((s) => s.status === "running");
  const completedCount = stages.filter((s) => s.status === "complete").length;

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      {/* Compact view: current stage + progress count */}
      {!expanded && (
        <button
          onClick={() => setExpanded(true)}
          className="flex items-center gap-1.5 hover:text-foreground transition-colors"
        >
          {currentStage && (
            <>
              <Loader2 className="h-3 w-3 animate-spin text-blue-500" />
              <span>{currentStage.name}</span>
            </>
          )}
          <span className="text-muted-foreground/70">
            ({completedCount}/{stages.length})
          </span>
          <span className="tabular-nums">{formatElapsed(elapsedS)}</span>
        </button>
      )}

      {/* Expanded view: all stages */}
      {expanded && (
        <div className="flex items-center gap-2">
          {stages.map((stage) => (
            <div
              key={stage.name}
              className="flex items-center gap-1"
              title={`${stage.name}: ${stage.status}${stage.elapsed_s !== null ? ` (${formatElapsed(stage.elapsed_s)})` : ""}`}
            >
              <StageIcon status={stage.status} />
              <span
                className={
                  stage.status === "running"
                    ? "text-foreground font-medium"
                    : ""
                }
              >
                {stage.name}
              </span>
              {stage.elapsed_s !== null && (
                <span className="tabular-nums text-muted-foreground/70">
                  {formatElapsed(stage.elapsed_s)}
                </span>
              )}
            </div>
          ))}
          <button
            onClick={() => setExpanded(false)}
            className="ml-1 hover:text-foreground"
          >
            <ChevronUp className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  );
}
