"use client";

import { useSummary } from "@/hooks/use-summaries";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { StructuredCards } from "./structured-cards";
import { MarkdownRenderer } from "./markdown-renderer";
import { EmptyState } from "./empty-state";
import { AlertCircle } from "lucide-react";

interface SummaryViewProps {
  selectedDate: string | null;
}

export function SummaryView({ selectedDate }: SummaryViewProps) {
  const { data, isLoading, isError, error, refetch } =
    useSummary(selectedDate);

  if (!selectedDate) {
    return (
      <EmptyState message="Select a date from the left panel to view a summary" />
    );
  }

  if (isLoading) {
    return <SummaryLoading />;
  }

  if (isError) {
    // 404 = no summary for this date
    if (error?.message?.includes("404")) {
      return <EmptyState date={selectedDate} />;
    }
    return (
      <div className="flex flex-col items-center justify-center gap-3 p-8 text-muted-foreground">
        <AlertCircle className="h-8 w-8 text-destructive opacity-60" />
        <p className="text-sm">Failed to load summary</p>
        <p className="text-xs opacity-60">{error?.message}</p>
        <button
          onClick={() => refetch()}
          className="mt-2 rounded-md bg-secondary px-3 py-1.5 text-xs font-medium transition-colors hover:bg-secondary/80"
        >
          Try again
        </button>
      </div>
    );
  }

  if (!data) {
    return <EmptyState date={selectedDate} />;
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <StructuredCards sidecar={data.sidecar} />

      {data.sidecar &&
        (data.sidecar.decisions.length > 0 ||
          data.sidecar.commitments.length > 0 ||
          data.sidecar.tasks.length > 0) && <Separator className="my-6" />}

      <MarkdownRenderer markdown={data.markdown} />
    </div>
  );
}

function SummaryLoading() {
  return (
    <div className="space-y-4 p-6">
      {/* Card skeletons */}
      <Skeleton className="h-24 w-full rounded-lg" />
      <Skeleton className="h-24 w-full rounded-lg" />
      <Skeleton className="h-24 w-full rounded-lg" />

      {/* Separator */}
      <div className="py-4">
        <Skeleton className="h-px w-full" />
      </div>

      {/* Markdown skeleton */}
      <div className="space-y-3">
        <Skeleton className="h-6 w-1/2" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-6 w-1/3 mt-6" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-4/5" />
      </div>
    </div>
  );
}
