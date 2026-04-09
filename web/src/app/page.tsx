"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { LeftNav } from "@/components/layout/left-nav";
import { RightSidebar } from "@/components/layout/right-sidebar";
import { SidebarRail } from "@/components/layout/sidebar-rail";
import { SummaryView } from "@/components/summary/summary-view";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { useUIStore } from "@/stores/ui-store";
import { useSummaryList, useSummary } from "@/hooks/use-summaries";

export default function Home() {
  const leftCollapsed = useUIStore((s) => s.leftNavCollapsed);
  const rightCollapsed = useUIStore((s) => s.rightSidebarCollapsed);
  const toggleLeftNav = useUIStore((s) => s.toggleLeftNav);
  const toggleRightSidebar = useUIStore((s) => s.toggleRightSidebar);

  const { data: summaryList } = useSummaryList();
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // Auto-select most recent date on load
  useEffect(() => {
    if (summaryList && summaryList.length > 0 && !selectedDate) {
      setSelectedDate(summaryList[0].date);
    }
  }, [summaryList, selectedDate]);

  const { data: summaryData, isLoading: summaryLoading } =
    useSummary(selectedDate);

  return (
    <AppShell
      leftNav={
        <ErrorBoundary>
          {leftCollapsed ? (
            <SidebarRail side="left" onExpand={toggleLeftNav} />
          ) : (
            <LeftNav onCollapse={toggleLeftNav}>
              <p className="p-4 text-sm text-muted-foreground">
                Date navigation coming in Plan 04
              </p>
            </LeftNav>
          )}
        </ErrorBoundary>
      }
      rightSidebar={
        <ErrorBoundary>
          {rightCollapsed ? (
            <SidebarRail side="right" onExpand={toggleRightSidebar} />
          ) : (
            <RightSidebar
              onCollapse={toggleRightSidebar}
              summary={summaryData}
              isLoading={summaryLoading}
            />
          )}
        </ErrorBoundary>
      }
    >
      <ErrorBoundary>
        <SummaryView selectedDate={selectedDate} />
      </ErrorBoundary>
    </AppShell>
  );
}
