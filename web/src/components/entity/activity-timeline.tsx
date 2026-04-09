"use client";

import { format, parseISO } from "date-fns";
import { TimelineEntry } from "./timeline-entry";
import type { ActivityDay } from "@/lib/types";

interface ActivityTimelineProps {
  activityByDate: ActivityDay[];
  onViewInSummary?: (date: string) => void;
}

export function ActivityTimeline({
  activityByDate,
  onViewInSummary,
}: ActivityTimelineProps) {
  if (activityByDate.length === 0) {
    return (
      <div className="space-y-2">
        <h2 className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
          Activity Timeline
        </h2>
        <p className="text-xs text-muted-foreground">No activity recorded</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
        Activity Timeline
      </h2>

      <div className="space-y-4">
        {activityByDate.map((day) => (
          <div key={day.date}>
            {/* Date header */}
            <h3 className="mb-2 text-xs font-medium text-muted-foreground">
              {format(parseISO(day.date), "EEEE, MMMM d, yyyy")}
            </h3>

            {/* Timeline entries with vertical line */}
            <div className="relative border-l-2 border-muted ml-1 space-y-1">
              {day.items.map((item, idx) => (
                <TimelineEntry
                  key={`${day.date}-${idx}`}
                  item={item}
                  onViewInSummary={onViewInSummary}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
