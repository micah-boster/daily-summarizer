"use client";

import { useQuery } from "@tanstack/react-query";
import { GitMerge } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useUIStore } from "@/stores/ui-store";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { MergeProposalResponse } from "@/lib/types";

export function MergeReviewButton() {
  const showMergeReview = useUIStore((s) => s.showMergeReview);
  const setShowMergeReview = useUIStore((s) => s.setShowMergeReview);

  const { data: proposals } = useQuery<MergeProposalResponse[]>({
    queryKey: ["merge-proposals"],
    queryFn: () => apiFetch<MergeProposalResponse[]>("/merge-proposals"),
    staleTime: 5 * 60 * 1000,
  });

  const count = proposals?.length ?? 0;

  // Don't show if no proposals
  if (count === 0 && !showMergeReview) return null;

  return (
    <button
      onClick={() => setShowMergeReview(!showMergeReview)}
      className={cn(
        "mx-3 mt-1 flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
        showMergeReview
          ? "bg-primary/10 text-primary"
          : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      <GitMerge className="h-3.5 w-3.5" />
      <span>Review Merges</span>
      {count > 0 && (
        <Badge variant="secondary" className="ml-auto h-4 min-w-4 px-1 text-[10px]">
          {count}
        </Badge>
      )}
    </button>
  );
}
