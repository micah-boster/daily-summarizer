"use client";

import { Video, CheckSquare } from "lucide-react";
import { format, parseISO } from "date-fns";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Daily date entry                                                   */
/* ------------------------------------------------------------------ */

interface DateListItemProps {
  date: string;
  meetingCount?: number | null;
  commitmentCount?: number | null;
  isSelected: boolean;
  onClick: () => void;
}

export function DateListItem({
  date,
  meetingCount,
  commitmentCount,
  isSelected,
  onClick,
}: DateListItemProps) {
  const formatted = format(parseISO(date), "EEE, MMM d");

  return (
    <button
      onClick={onClick}
      data-kb-item
      className={cn(
        "flex w-full flex-col gap-0.5 rounded-md px-3 py-2 text-left text-sm transition-colors",
        isSelected
          ? "bg-accent text-accent-foreground"
          : "hover:bg-accent/50",
      )}
    >
      <span className="font-medium">{formatted}</span>
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        {meetingCount != null && meetingCount > 0 && (
          <span className="flex items-center gap-1">
            <Video className="h-3 w-3" />
            {meetingCount}
          </span>
        )}
        {commitmentCount != null && commitmentCount > 0 && (
          <span className="flex items-center gap-1">
            <CheckSquare className="h-3 w-3" />
            {commitmentCount}
          </span>
        )}
      </div>
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  Weekly entry                                                       */
/* ------------------------------------------------------------------ */

interface WeeklyListItemProps {
  weekLabel: string;
  dailyCount: number;
  isSelected: boolean;
  onClick: () => void;
}

export function WeeklyListItem({
  weekLabel,
  dailyCount,
  isSelected,
  onClick,
}: WeeklyListItemProps) {
  return (
    <button
      onClick={onClick}
      data-kb-item
      className={cn(
        "flex w-full flex-col gap-0.5 rounded-md px-3 py-2 text-left text-sm transition-colors",
        isSelected
          ? "bg-accent text-accent-foreground"
          : "hover:bg-accent/50",
      )}
    >
      <span className="font-medium">{weekLabel}</span>
      <span className="text-xs text-muted-foreground">
        {dailyCount} daily {dailyCount === 1 ? "summary" : "summaries"}
      </span>
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  Monthly entry                                                      */
/* ------------------------------------------------------------------ */

interface MonthlyListItemProps {
  monthLabel: string;
  isSelected: boolean;
  onClick: () => void;
}

export function MonthlyListItem({
  monthLabel,
  isSelected,
  onClick,
}: MonthlyListItemProps) {
  return (
    <button
      onClick={onClick}
      data-kb-item
      className={cn(
        "flex w-full rounded-md px-3 py-2 text-left text-sm font-medium transition-colors",
        isSelected
          ? "bg-accent text-accent-foreground"
          : "hover:bg-accent/50",
      )}
    >
      {monthLabel}
    </button>
  );
}
