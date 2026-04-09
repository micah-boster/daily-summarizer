"use client";

import { format, parseISO } from "date-fns";
import type { ActivityItemResponse } from "@/lib/types";

interface CommitmentsSectionProps {
  commitments: ActivityItemResponse[];
}

export function CommitmentsSection({ commitments }: CommitmentsSectionProps) {
  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
        Open Commitments
      </h2>

      {commitments.length === 0 ? (
        <p className="text-xs text-muted-foreground">No open commitments</p>
      ) : (
        <div className="space-y-2">
          {commitments.map((c, i) => (
            <div
              key={i}
              className="rounded-md border px-3 py-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">
                  {c.source_date
                    ? format(parseISO(c.source_date), "MMM d, yyyy")
                    : ""}
                </span>
                <SignificanceBadge score={c.significance_score} />
              </div>
              <p className="mt-1 text-sm leading-snug">
                {truncate(c.context_snippet ?? "", 150)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SignificanceBadge({ score }: { score: number }) {
  const { label, className } = getSignificance(score);
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${className}`}>
      {label}
    </span>
  );
}

function getSignificance(score: number) {
  if (score >= 3.0) return { label: "High", className: "bg-red-100 text-red-700" };
  if (score >= 1.5) return { label: "Medium", className: "bg-yellow-100 text-yellow-700" };
  return { label: "Low", className: "bg-gray-100 text-gray-700" };
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trimEnd() + "...";
}
