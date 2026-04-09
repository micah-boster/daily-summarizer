"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Sun, Moon, Monitor, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useUIStore } from "@/stores/ui-store";
import { RunTrigger } from "@/components/pipeline/run-trigger";
import { RunProgress } from "@/components/pipeline/run-progress";
import { usePipelineStore } from "@/stores/pipeline-store";

const THEME_CYCLE = ["system", "light", "dark"] as const;

function ThemeToggle() {
  const [mounted, setMounted] = useState(false);
  const { theme, setTheme } = useTheme();

  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return <Button variant="ghost" size="icon" className="h-7 w-7" disabled />;
  }

  const current = theme ?? "system";
  const nextIndex = (THEME_CYCLE.indexOf(current as (typeof THEME_CYCLE)[number]) + 1) % THEME_CYCLE.length;

  const Icon = current === "light" ? Sun : current === "dark" ? Moon : Monitor;

  return (
    <Button
      variant="ghost"
      size="icon"
      className="h-7 w-7"
      onClick={() => setTheme(THEME_CYCLE[nextIndex])}
      title={`Theme: ${current}`}
    >
      <Icon className="h-4 w-4" />
    </Button>
  );
}

export function StatusBar() {
  const status = usePipelineStore((s) => s.status);
  const elapsedS = usePipelineStore((s) => s.elapsedS);
  const toggleConfigPanel = useUIStore((s) => s.toggleConfigPanel);

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 flex h-10 items-center justify-between border-t border-border bg-card/80 px-4 backdrop-blur-sm">
      {/* Left: trigger + progress */}
      <div className="flex items-center gap-3">
        <RunTrigger />
        <RunProgress />
      </div>

      {/* Right: settings gear + theme toggle + elapsed */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={toggleConfigPanel}
          aria-label="Settings"
        >
          <Settings className="size-4" />
        </Button>
        <ThemeToggle />
        {status === "running" && (
          <span className="tabular-nums">{elapsedS.toFixed(1)}s elapsed</span>
        )}
      </div>
    </div>
  );
}
