"use client";

import type { ReactNode } from "react";
import { useUIStore } from "@/stores/ui-store";

interface AppShellProps {
  leftNav: ReactNode;
  children: ReactNode;
  rightSidebar: ReactNode;
}

export function AppShell({ leftNav, children, rightSidebar }: AppShellProps) {
  const leftCollapsed = useUIStore((s) => s.leftNavCollapsed);
  const rightCollapsed = useUIStore((s) => s.rightSidebarCollapsed);

  const bothCollapsed = leftCollapsed && rightCollapsed;

  return (
    <div
      className="grid h-screen min-w-[1024px] pb-10"
      style={{
        gridTemplateColumns: `${leftCollapsed ? "48px" : "280px"} 1fr ${rightCollapsed ? "48px" : "300px"}`,
      }}
    >
      {/* Left sidebar / rail */}
      <div className="overflow-hidden">{leftNav}</div>

      {/* Center content */}
      <div className="overflow-y-auto">
        <div
          className={
            bothCollapsed ? "mx-auto max-w-[900px]" : "h-full w-full"
          }
        >
          {children}
        </div>
      </div>

      {/* Right sidebar / rail */}
      <div className="overflow-hidden">{rightSidebar}</div>
    </div>
  );
}
