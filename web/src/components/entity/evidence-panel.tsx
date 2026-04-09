"use client";

import { format, parseISO } from "date-fns";
import { MessageSquare, Gavel, Handshake } from "lucide-react";
import type { ActivityItemResponse } from "@/lib/types";

interface EvidencePanelProps {
  item: ActivityItemResponse;
  onViewInSummary?: (date: string) => void;
}

const SOURCE_ICONS: Record<string, typeof MessageSquare> = {
  substance: MessageSquare,
  decision: Gavel,
  commitment: Handshake,
};

export function EvidencePanel({ item, onViewInSummary }: EvidencePanelProps) {
  const Icon = SOURCE_ICONS[item.source_type] ?? MessageSquare;
  const confidencePct = Math.round(item.confidence * 100);

  return (
    <div className="rounded-md border bg-muted/20 px-4 py-3 space-y-3">
      {/* Full snippet */}
      <p className="text-sm leading-relaxed">
        {item.context_snippet ?? "No details available"}
      </p>

      {/* Metadata row */}
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <Icon className="h-3 w-3" />
          <span className="capitalize">{item.source_type}</span>
        </span>
        <span>
          {item.source_date
            ? format(parseISO(item.source_date), "MMM d, yyyy")
            : ""}
        </span>
        <ConfidenceBadge confidence={confidencePct} />
      </div>

      {/* View in summary link */}
      {onViewInSummary && item.source_date && (
        <button
          onClick={() => onViewInSummary(item.source_date)}
          className="text-xs font-medium text-blue-600 hover:text-blue-800 hover:underline dark:text-blue-400 dark:hover:text-blue-300"
        >
          View in summary
        </button>
      )}
    </div>
  );
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  let colorClasses: string;
  if (confidence > 80) {
    colorClasses = "bg-green-100 text-green-700";
  } else if (confidence >= 50) {
    colorClasses = "bg-yellow-100 text-yellow-700";
  } else {
    colorClasses = "bg-red-100 text-red-700";
  }

  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${colorClasses}`}>
      {confidence}%
    </span>
  );
}
