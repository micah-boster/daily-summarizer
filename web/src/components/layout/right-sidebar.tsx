"use client";

import type { ReactNode } from "react";
import { ChevronRight, Video, Calendar, BarChart3 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { format, parseISO } from "date-fns";
import type { SummaryResponse } from "@/lib/types";
import { EntitySidebar } from "./entity-sidebar";

interface RightSidebarProps {
  onCollapse: () => void;
  summary?: SummaryResponse | null;
  isLoading?: boolean;
  children?: ReactNode;
  activeTab?: "summaries" | "entities" | "runs";
  entityId?: string | null;
}

export function RightSidebar({
  onCollapse,
  summary,
  isLoading,
  children,
  activeTab = "summaries",
  entityId,
}: RightSidebarProps) {
  const showEntity = activeTab === "entities" && entityId;
  const headerTitle = showEntity ? "Entity Details" : "Summary Info";

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b border-border px-4">
        <span className="text-sm font-semibold">{headerTitle}</span>
        <button
          onClick={onCollapse}
          className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          aria-label="Collapse right sidebar"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4">
        {showEntity ? (
          <EntitySidebar entityId={entityId} />
        ) : activeTab === "entities" ? (
          <p className="text-xs text-muted-foreground">
            Select an entity to see details
          </p>
        ) : isLoading ? (
          <MetadataLoading />
        ) : summary?.sidecar ? (
          <SummaryMetadata summary={summary} />
        ) : children ? (
          children
        ) : (
          <p className="text-xs text-muted-foreground">
            No structured data available for this date
          </p>
        )}
      </div>
    </div>
  );
}

function SummaryMetadata({ summary }: { summary: SummaryResponse }) {
  const sidecar = summary.sidecar;
  if (!sidecar) return null;

  const totalItems =
    (sidecar.decisions?.length ?? 0) + (sidecar.commitments?.length ?? 0) + (sidecar.tasks?.length ?? 0);
  const entityMentions = (sidecar.entity_summary ?? []).reduce(
    (sum, e) => sum + e.mention_count,
    0,
  );

  return (
    <div className="space-y-5">
      {/* Sources Used */}
      <MetadataSection title="Sources">
        <div className="space-y-1.5">
          {(sidecar.source_meetings ?? []).map((m, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              {m.has_transcript ? (
                <Video className="h-3 w-3 text-muted-foreground" />
              ) : (
                <Calendar className="h-3 w-3 text-muted-foreground" />
              )}
              <span className="truncate">{m.title}</span>
            </div>
          ))}
          <p className="mt-1 text-xs text-muted-foreground">
            {sidecar.meeting_count ?? 0} meetings
          </p>
        </div>
      </MetadataSection>

      {/* Extraction Stats */}
      <MetadataSection title="Extracted">
        <div className="grid grid-cols-2 gap-2">
          <StatBox label="Items" value={totalItems} />
          <StatBox label="Entities" value={entityMentions} />
          <StatBox label="Decisions" value={sidecar.decisions.length} />
          <StatBox label="Commitments" value={sidecar.commitments.length} />
        </div>
      </MetadataSection>

      {/* Pipeline Info */}
      <MetadataSection title="Pipeline">
        <div className="space-y-1 text-xs text-muted-foreground">
          <p>
            Generated:{" "}
            {formatTimestamp(sidecar.generated_at)}
          </p>
          <p>Date: {sidecar.date}</p>
        </div>
      </MetadataSection>

      {/* Quality */}
      <MetadataSection title="Quality">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-3 w-3 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">
            {sidecar.transcript_count ?? 0}/{sidecar.meeting_count ?? 0} meetings with
            transcripts
          </span>
        </div>
      </MetadataSection>
    </div>
  );
}

function MetadataSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {title}
      </h4>
      {children}
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-muted/50 px-2 py-1.5 text-center">
      <p className="text-lg font-semibold leading-none">{value}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

function MetadataLoading() {
  return (
    <div className="space-y-5">
      <div>
        <Skeleton className="mb-2 h-3 w-16" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="mt-1 h-4 w-3/4" />
      </div>
      <div>
        <Skeleton className="mb-2 h-3 w-20" />
        <div className="grid grid-cols-2 gap-2">
          <Skeleton className="h-12 rounded-md" />
          <Skeleton className="h-12 rounded-md" />
        </div>
      </div>
      <div>
        <Skeleton className="mb-2 h-3 w-16" />
        <Skeleton className="h-4 w-full" />
      </div>
    </div>
  );
}

function formatTimestamp(ts: string): string {
  try {
    return format(parseISO(ts), "MMM d, yyyy h:mm a");
  } catch {
    return ts;
  }
}
