"use client";

import { useMemo } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { format, parseISO } from "date-fns";
import { DatePicker } from "./date-picker";
import { cn } from "@/lib/utils";

interface NavHeaderProps {
  selectedDate: string | null;
  availableDates: string[];
  onDateChange: (date: string) => void;
}

export function NavHeader({
  selectedDate,
  availableDates,
  onDateChange,
}: NavHeaderProps) {
  const { prevDate, nextDate } = useMemo(() => {
    if (!selectedDate || availableDates.length === 0) {
      return { prevDate: null, nextDate: null };
    }
    const idx = availableDates.indexOf(selectedDate);
    // availableDates are sorted most-recent-first
    return {
      nextDate: idx > 0 ? availableDates[idx - 1] : null,
      prevDate: idx < availableDates.length - 1 ? availableDates[idx + 1] : null,
    };
  }, [selectedDate, availableDates]);

  const displayDate = selectedDate
    ? format(parseISO(selectedDate), "MMMM d, yyyy")
    : "No date selected";

  return (
    <div className="flex items-center justify-between border-b px-3 py-3">
      <button
        onClick={() => prevDate && onDateChange(prevDate)}
        disabled={!prevDate}
        className={cn(
          "flex h-7 w-7 items-center justify-center rounded-md transition-colors",
          prevDate
            ? "cursor-pointer text-muted-foreground hover:bg-accent hover:text-foreground"
            : "cursor-not-allowed opacity-30",
        )}
        aria-label="Previous date"
      >
        <ChevronLeft className="h-4 w-4" />
      </button>

      <span className="text-xs font-medium">{displayDate}</span>

      <div className="flex items-center gap-1">
        <button
          onClick={() => nextDate && onDateChange(nextDate)}
          disabled={!nextDate}
          className={cn(
            "flex h-7 w-7 items-center justify-center rounded-md transition-colors",
            nextDate
              ? "cursor-pointer text-muted-foreground hover:bg-accent hover:text-foreground"
              : "cursor-not-allowed opacity-30",
          )}
          aria-label="Next date"
        >
          <ChevronRight className="h-4 w-4" />
        </button>

        <DatePicker
          availableDates={availableDates}
          selectedDate={selectedDate}
          onSelect={onDateChange}
        />
      </div>
    </div>
  );
}
