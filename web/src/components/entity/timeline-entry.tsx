"use client";

import { useState } from "react";
import { format, parseISO } from "date-fns";
import { MessageSquare, Gavel, Handshake, ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { EvidencePanel } from "./evidence-panel";
import type { ActivityItemResponse } from "@/lib/types";

interface TimelineEntryProps {
  item: ActivityItemResponse;
  onViewInSummary?: (date: string) => void;
}

const SOURCE_ICONS: Record<string, typeof MessageSquare> = {
  substance: MessageSquare,
  decision: Gavel,
  commitment: Handshake,
};

export function TimelineEntry({ item, onViewInSummary }: TimelineEntryProps) {
  const [expanded, setExpanded] = useState(false);
  const Icon = SOURCE_ICONS[item.source_type] ?? MessageSquare;

  return (
    <div className="relative pl-6">
      {/* Timeline dot */}
      <div className="absolute left-0 top-2.5 h-2.5 w-2.5 rounded-full border-2 border-muted-foreground/30 bg-background" />

      {/* Entry header - clickable */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-accent/50"
      >
        <Icon className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
        <div className="flex-1 min-w-0">
          <p className="text-sm leading-snug">
            {truncate(item.context_snippet ?? "No details", 80)}
          </p>
        </div>
        <SignificanceBadge score={item.significance_score} />
        {expanded ? (
          <ChevronDown className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
        )}
      </button>

      {/* Expanded evidence */}
      {expanded && (
        <div className="ml-2 mt-1 mb-2">
          <EvidencePanel item={item} onViewInSummary={onViewInSummary} />
        </div>
      )}
    </div>
  );
}

function SignificanceBadge({ score }: { score: number }) {
  const { label, className } = getSignificance(score);
  return (
    <span className={cn("flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium", className)}>
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
