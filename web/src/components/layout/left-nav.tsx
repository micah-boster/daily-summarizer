"use client";

import type { ReactNode } from "react";
import { ChevronLeft } from "lucide-react";

interface LeftNavProps {
  onCollapse: () => void;
  children?: ReactNode;
}

export function LeftNav({ onCollapse, children }: LeftNavProps) {
  return (
    <div className="flex h-full flex-col border-r bg-background">
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b px-4">
        <span className="text-sm font-semibold">Daily Summarizer</span>
        <button
          onClick={onCollapse}
          className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          aria-label="Collapse left sidebar"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">{children}</div>
    </div>
  );
}
