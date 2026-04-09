"use client";

import { Calendar, CalendarRange, CalendarDays, ChevronLeft, GitMerge } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { NavHeader } from "@/components/nav/nav-header";
import { NavTabSwitcher } from "@/components/nav/nav-tab-switcher";
import { EntityFilterBar } from "@/components/nav/entity-filter-bar";
import { EntityList } from "@/components/nav/entity-list";
import { MergeReviewButton } from "@/components/merge/merge-review-button";
import { RunHistory } from "@/components/pipeline/run-history";
import { DateGroup } from "@/components/nav/date-group";
import {
  DateListItem,
  WeeklyListItem,
  MonthlyListItem,
} from "@/components/nav/date-list";
import {
  useSummaryList,
  useWeeklyList,
  useMonthlyList,
} from "@/hooks/use-summaries";
import { useUIStore } from "@/stores/ui-store";

interface LeftNavProps {
  selectedDate: string | null;
  selectedType: "daily" | "weekly" | "monthly";
  selectedKey: string | null;
  onSelectDaily: (date: string) => void;
  onSelectWeekly: (year: number, week: number) => void;
  onSelectMonthly: (year: number, month: number) => void;
  onCollapse: () => void;
}

export function LeftNav({
  selectedDate,
  selectedType,
  selectedKey,
  onSelectDaily,
  onSelectWeekly,
  onSelectMonthly,
  onCollapse,
}: LeftNavProps) {
  const activeTab = useUIStore((s) => s.activeTab);

  const { data: dailyList, isLoading: dailyLoading } = useSummaryList();
  const { data: weeklyList, isLoading: weeklyLoading } = useWeeklyList();
  const { data: monthlyList, isLoading: monthlyLoading } = useMonthlyList();

  const availableDates = dailyList?.map((d) => d.date) ?? [];

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b border-border px-4">
        <span className="text-sm font-semibold tracking-tight">Daily Summarizer</span>
        <button
          onClick={onCollapse}
          className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          aria-label="Collapse left sidebar"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
      </div>

      {/* Tab switcher */}
      <NavTabSwitcher />

      {/* Summaries content */}
      {activeTab === "summaries" && (
        <>
          <NavHeader
            selectedDate={selectedDate}
            availableDates={availableDates}
            onDateChange={onSelectDaily}
          />

          <div className="flex-1 overflow-y-auto py-2">
            {/* Daily group */}
            {dailyLoading ? (
              <NavSkeleton />
            ) : dailyList && dailyList.length > 0 ? (
              <DateGroup
                title="Daily"
                icon={Calendar}
                count={dailyList.length}
                groupId="daily"
              >
                {dailyList.map((item) => (
                  <DateListItem
                    key={item.date}
                    date={item.date}
                    meetingCount={item.meeting_count}
                    commitmentCount={item.commitment_count}
                    isSelected={
                      selectedType === "daily" && selectedDate === item.date
                    }
                    onClick={() => onSelectDaily(item.date)}
                  />
                ))}
              </DateGroup>
            ) : null}

            {/* Weekly group */}
            {weeklyLoading ? (
              <NavSkeleton />
            ) : weeklyList && weeklyList.length > 0 ? (
              <DateGroup
                title="Weekly"
                icon={CalendarRange}
                count={weeklyList.length}
                groupId="weekly"
              >
                {weeklyList.map((item) => {
                  const key = `w-${item.year}-${item.week_number}`;
                  return (
                    <WeeklyListItem
                      key={key}
                      weekLabel={item.week_label}
                      dailyCount={item.daily_count}
                      isSelected={selectedType === "weekly" && selectedKey === key}
                      onClick={() =>
                        onSelectWeekly(item.year, item.week_number)
                      }
                    />
                  );
                })}
              </DateGroup>
            ) : null}

            {/* Monthly group */}
            {monthlyLoading ? (
              <NavSkeleton />
            ) : monthlyList && monthlyList.length > 0 ? (
              <DateGroup
                title="Monthly"
                icon={CalendarDays}
                count={monthlyList.length}
                groupId="monthly"
              >
                {monthlyList.map((item) => {
                  const key = `m-${item.year}-${item.month}`;
                  return (
                    <MonthlyListItem
                      key={key}
                      monthLabel={item.month_label}
                      isSelected={
                        selectedType === "monthly" && selectedKey === key
                      }
                      onClick={() => onSelectMonthly(item.year, item.month)}
                    />
                  );
                })}
              </DateGroup>
            ) : null}
          </div>
        </>
      )}

      {/* Entities content */}
      {activeTab === "entities" && (
        <>
          <EntityFilterBar />
          <MergeReviewButton />
          <div className="flex-1 overflow-y-auto py-2">
            <EntityList />
          </div>
        </>
      )}

      {/* Runs content */}
      {activeTab === "runs" && (
        <div className="flex-1 overflow-y-auto py-2">
          <RunHistory />
        </div>
      )}
    </div>
  );
}

function NavSkeleton() {
  return (
    <div className="space-y-2 px-3 py-2">
      <Skeleton className="h-4 w-16" />
      <Skeleton className="h-10 w-full rounded-md" />
      <Skeleton className="h-10 w-full rounded-md" />
      <Skeleton className="h-10 w-full rounded-md" />
    </div>
  );
}
