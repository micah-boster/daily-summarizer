"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { LeftNav } from "@/components/layout/left-nav";
import { RightSidebar } from "@/components/layout/right-sidebar";
import { SidebarRail } from "@/components/layout/sidebar-rail";
import { SummaryView } from "@/components/summary/summary-view";
import { MarkdownRenderer } from "@/components/summary/markdown-renderer";
import { EmptyState } from "@/components/summary/empty-state";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { Skeleton } from "@/components/ui/skeleton";
import { useUIStore } from "@/stores/ui-store";
import {
  useSummaryList,
  useSummary,
  useWeeklyRollup,
  useMonthlyRollup,
} from "@/hooks/use-summaries";

type ViewType = "daily" | "weekly" | "monthly";

export default function Home() {
  const leftCollapsed = useUIStore((s) => s.leftNavCollapsed);
  const rightCollapsed = useUIStore((s) => s.rightSidebarCollapsed);
  const toggleLeftNav = useUIStore((s) => s.toggleLeftNav);
  const toggleRightSidebar = useUIStore((s) => s.toggleRightSidebar);

  const { data: summaryList } = useSummaryList();

  // Selection state
  const [selectedType, setSelectedType] = useState<ViewType>("daily");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [selectedWeekly, setSelectedWeekly] = useState<{
    year: number;
    week: number;
  } | null>(null);
  const [selectedMonthly, setSelectedMonthly] = useState<{
    year: number;
    month: number;
  } | null>(null);

  // Auto-select most recent date on load
  useEffect(() => {
    if (summaryList && summaryList.length > 0 && !selectedDate) {
      setSelectedDate(summaryList[0].date);
    }
  }, [summaryList, selectedDate]);

  // Summary data for right sidebar (daily only)
  const { data: summaryData, isLoading: summaryLoading } =
    useSummary(selectedType === "daily" ? selectedDate : null);

  // Derive selected key for left nav highlighting
  const selectedKey =
    selectedType === "weekly" && selectedWeekly
      ? `w-${selectedWeekly.year}-${selectedWeekly.week}`
      : selectedType === "monthly" && selectedMonthly
        ? `m-${selectedMonthly.year}-${selectedMonthly.month}`
        : null;

  const handleSelectDaily = (date: string) => {
    setSelectedType("daily");
    setSelectedDate(date);
    setSelectedWeekly(null);
    setSelectedMonthly(null);
  };

  const handleSelectWeekly = (year: number, week: number) => {
    setSelectedType("weekly");
    setSelectedWeekly({ year, week });
    setSelectedMonthly(null);
  };

  const handleSelectMonthly = (year: number, month: number) => {
    setSelectedType("monthly");
    setSelectedMonthly({ year, month });
    setSelectedWeekly(null);
  };

  return (
    <AppShell
      leftNav={
        <ErrorBoundary>
          {leftCollapsed ? (
            <SidebarRail side="left" onExpand={toggleLeftNav} />
          ) : (
            <LeftNav
              selectedDate={selectedDate}
              selectedType={selectedType}
              selectedKey={selectedKey}
              onSelectDaily={handleSelectDaily}
              onSelectWeekly={handleSelectWeekly}
              onSelectMonthly={handleSelectMonthly}
              onCollapse={toggleLeftNav}
            />
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
              summary={selectedType === "daily" ? summaryData : undefined}
              isLoading={selectedType === "daily" ? summaryLoading : false}
            >
              {selectedType !== "daily" && (
                <p className="text-xs text-muted-foreground">
                  Select a daily summary for detailed metadata
                </p>
              )}
            </RightSidebar>
          )}
        </ErrorBoundary>
      }
    >
      <ErrorBoundary>
        {selectedType === "daily" && (
          <SummaryView selectedDate={selectedDate} />
        )}
        {selectedType === "weekly" && selectedWeekly && (
          <WeeklyView
            year={selectedWeekly.year}
            week={selectedWeekly.week}
          />
        )}
        {selectedType === "monthly" && selectedMonthly && (
          <MonthlyView
            year={selectedMonthly.year}
            month={selectedMonthly.month}
          />
        )}
      </ErrorBoundary>
    </AppShell>
  );
}

/* ------------------------------------------------------------------ */
/*  Rollup views — fetch markdown and render                           */
/* ------------------------------------------------------------------ */

function WeeklyView({ year, week }: { year: number; week: number }) {
  const { data, isLoading, isError } = useWeeklyRollup(year, week);

  if (isLoading) {
    return (
      <div className="space-y-3 p-6">
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-full" />
      </div>
    );
  }

  if (isError || !data) {
    return <EmptyState message={`No weekly summary for week ${week}, ${year}`} />;
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <MarkdownRenderer markdown={data.markdown} />
    </div>
  );
}

function MonthlyView({ year, month }: { year: number; month: number }) {
  const { data, isLoading, isError } = useMonthlyRollup(year, month);

  if (isLoading) {
    return (
      <div className="space-y-3 p-6">
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-full" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <EmptyState
        message={`No monthly summary for ${new Date(year, month - 1).toLocaleDateString("en-US", { month: "long", year: "numeric" })}`}
      />
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <MarkdownRenderer markdown={data.markdown} />
    </div>
  );
}
