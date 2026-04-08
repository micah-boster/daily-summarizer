"use client";

import { Calendar, Info, ChevronLeft, ChevronRight } from "lucide-react";

interface SidebarRailProps {
  side: "left" | "right";
  onExpand: () => void;
}

export function SidebarRail({ side, onExpand }: SidebarRailProps) {
  const isLeft = side === "left";
  const ExpandIcon = isLeft ? ChevronRight : ChevronLeft;

  return (
    <div
      className={`flex h-full w-12 flex-col items-center gap-2 pt-4 ${
        isLeft ? "border-r" : "border-l"
      } bg-background`}
    >
      <button
        onClick={onExpand}
        className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        aria-label={`Expand ${side} sidebar`}
      >
        {isLeft ? (
          <Calendar className="h-4 w-4" />
        ) : (
          <Info className="h-4 w-4" />
        )}
      </button>

      <div className="flex-1" />

      <button
        onClick={onExpand}
        className="mb-4 flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        aria-label={`Expand ${side} sidebar`}
      >
        <ExpandIcon className="h-4 w-4" />
      </button>
    </div>
  );
}
