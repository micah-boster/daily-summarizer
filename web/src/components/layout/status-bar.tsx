"use client";

import { RunTrigger } from "@/components/pipeline/run-trigger";
import { RunProgress } from "@/components/pipeline/run-progress";
import { usePipelineStore } from "@/stores/pipeline-store";

export function StatusBar() {
  const status = usePipelineStore((s) => s.status);
  const elapsedS = usePipelineStore((s) => s.elapsedS);

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 flex h-10 items-center justify-between border-t bg-muted/50 px-4 backdrop-blur-sm">
      {/* Left: trigger + progress */}
      <div className="flex items-center gap-3">
        <RunTrigger />
        <RunProgress />
      </div>

      {/* Right: total elapsed when running */}
      <div className="text-xs text-muted-foreground">
        {status === "running" && (
          <span className="tabular-nums">{elapsedS.toFixed(1)}s elapsed</span>
        )}
      </div>
    </div>
  );
}
