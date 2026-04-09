"use client";

import type { ReactNode } from "react";
import { useUIStore } from "@/stores/ui-store";
import { useKeyboardNav } from "@/hooks/use-keyboard-nav";
import { cn } from "@/lib/utils";

interface AppShellProps {
  leftNav: ReactNode;
  children: ReactNode;
  rightSidebar: ReactNode;
}

export function AppShell({ leftNav, children, rightSidebar }: AppShellProps) {
  const leftCollapsed = useUIStore((s) => s.leftNavCollapsed);
  const rightCollapsed = useUIStore((s) => s.rightSidebarCollapsed);
  const focusedColumn = useUIStore((s) => s.focusedColumn);

  const bothCollapsed = leftCollapsed && rightCollapsed;

  // Mount global keyboard navigation
  useKeyboardNav();

  return (
    <div
      className="grid h-screen min-w-[1024px] pb-10"
      style={{
        gridTemplateColumns: `${leftCollapsed ? "48px" : "280px"} 1fr ${rightCollapsed ? "48px" : "300px"}`,
      }}
    >
      {/* Left sidebar / rail */}
      <div
        data-kb-column="left"
        className={cn(
          "overflow-hidden border-r border-border transition-colors",
          focusedColumn === "left" && "border-r-primary/20",
        )}
      >
        {leftNav}
      </div>

      {/* Center content */}
      <div
        data-kb-column="center"
        className={cn(
          "overflow-y-auto transition-colors",
          focusedColumn === "center" && "border-x border-primary/20",
        )}
      >
        <div
          className={cn(
            "px-6 py-4",
            bothCollapsed ? "mx-auto max-w-[900px]" : "h-full w-full",
          )}
        >
          {children}
        </div>
      </div>

      {/* Right sidebar / rail */}
      <div
        data-kb-column="right"
        className={cn(
          "overflow-hidden border-l border-border transition-colors",
          focusedColumn === "right" && "border-l-primary/20",
        )}
      >
        {rightSidebar}
      </div>
    </div>
  );
}
