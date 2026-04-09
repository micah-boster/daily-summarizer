"use client";

import { format, parseISO, differenceInDays } from "date-fns";
import type { ActivityItemResponse, ActivityDay } from "@/lib/types";

interface HighlightsSectionProps {
  totalMentions: number;
  activityByDate: ActivityDay[];
  highlights: ActivityItemResponse[];
}

export function HighlightsSection({
  totalMentions,
  activityByDate,
  highlights,
}: HighlightsSectionProps) {
  const daysActive = activityByDate.length;
  const lastSeenDate =
    activityByDate.length > 0 ? activityByDate[0].date : null;

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
        Highlights
      </h2>

      {/* Stat boxes */}
      <div className="grid grid-cols-3 gap-2">
        <StatBox label="Mentions" value={totalMentions} />
        <StatBox label="Days Active" value={daysActive} />
        <StatBox
          label="Last Seen"
          value={
            lastSeenDate
              ? format(parseISO(lastSeenDate), "MMM d")
              : "N/A"
          }
        />
      </div>

      {/* Top highlights */}
      {highlights.length > 0 && (
        <div className="space-y-2">
          {highlights.slice(0, 3).map((h, i) => (
            <div
              key={i}
              className="rounded-md border bg-muted/30 px-3 py-2"
            >
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="capitalize">{h.source_type}</span>
                <span>
                  {h.source_date
                    ? format(parseISO(h.source_date), "MMM d, yyyy")
                    : ""}
                </span>
              </div>
              <p className="mt-1 text-sm leading-snug">
                {truncate(h.context_snippet ?? "", 120)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md bg-muted/50 px-2 py-1.5 text-center">
      <p className="text-lg font-semibold leading-none">{value}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trimEnd() + "...";
}
