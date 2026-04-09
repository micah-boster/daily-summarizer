"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, SkipForward, X, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

import { apiFetch, apiMutate } from "@/lib/api";
import type { MergeProposalResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { MergePrimaryPicker } from "./merge-primary-picker";

export function MergeReviewPanel() {
  const queryClient = useQueryClient();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedPrimaryId, setSelectedPrimaryId] = useState<string | null>(
    null,
  );

  const {
    data: proposals,
    isLoading,
    isError,
  } = useQuery<MergeProposalResponse[]>({
    queryKey: ["merge-proposals"],
    queryFn: () => apiFetch<MergeProposalResponse[]>("/merge-proposals"),
  });

  const approveMutation = useMutation({
    mutationFn: (params: { proposalId: string; primaryEntityId: string }) =>
      apiMutate<MergeProposalResponse>(
        `/merge-proposals/${params.proposalId}/approve`,
        {
          method: "POST",
          body: { primary_entity_id: params.primaryEntityId },
        },
      ),
    onSuccess: () => {
      toast.success("Entities merged successfully");
      queryClient.invalidateQueries({ queryKey: ["entities"] });
      queryClient.invalidateQueries({ queryKey: ["merge-proposals"] });
      advance();
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to approve merge");
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (proposalId: string) =>
      apiMutate<MergeProposalResponse>(
        `/merge-proposals/${proposalId}/reject`,
        { method: "POST" },
      ),
    onSuccess: () => {
      toast.success("Proposal rejected");
      queryClient.invalidateQueries({ queryKey: ["merge-proposals"] });
      advance();
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to reject proposal");
    },
  });

  function advance() {
    setSelectedPrimaryId(null);
    setCurrentIndex((prev) => prev + 1);
  }

  function getProposalId(proposal: MergeProposalResponse): string {
    // Fresh proposals use source:target encoded IDs
    if (proposal.proposal_id) return proposal.proposal_id;
    return `${proposal.source_entity.entity_id}:${proposal.target_entity.entity_id}`;
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl space-y-6 p-8">
        <Skeleton className="h-6 w-48" />
        <div className="flex gap-3">
          <Skeleton className="h-48 flex-1 rounded-xl" />
          <Skeleton className="h-48 flex-1 rounded-xl" />
        </div>
        <div className="flex gap-3">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-8 w-24" />
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="mx-auto max-w-3xl p-8">
        <p className="text-sm text-destructive">
          Failed to load merge proposals. Please try again.
        </p>
      </div>
    );
  }

  // No proposals at all
  if (!proposals || proposals.length === 0) {
    return <EmptyMergeState message="No merge proposals to review" />;
  }

  // All reviewed
  if (currentIndex >= proposals.length) {
    return <EmptyMergeState message="All caught up" />;
  }

  const current = proposals[currentIndex];
  const proposalId = getProposalId(current);
  const isBusy = approveMutation.isPending || rejectMutation.isPending;

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-8">
      {/* Progress indicator */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Review Merge Proposals</h2>
        <span className="text-sm text-muted-foreground">
          Reviewing {currentIndex + 1} of {proposals.length} proposals
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1 w-full rounded-full bg-muted">
        <div
          className="h-1 rounded-full bg-primary transition-all"
          style={{
            width: `${((currentIndex + 1) / proposals.length) * 100}%`,
          }}
        />
      </div>

      {/* Primary picker */}
      <MergePrimaryPicker
        sourceEntity={current.source_entity}
        targetEntity={current.target_entity}
        sourceAliases={[]}
        targetAliases={[]}
        score={current.score}
        selectedPrimaryId={selectedPrimaryId}
        onSelectPrimary={setSelectedPrimaryId}
      />

      {/* Action buttons */}
      <div className="flex items-center gap-3 pt-2">
        <Button
          disabled={!selectedPrimaryId || isBusy}
          onClick={() => {
            if (!selectedPrimaryId) return;
            approveMutation.mutate({
              proposalId,
              primaryEntityId: selectedPrimaryId,
            });
          }}
        >
          <Check className="h-4 w-4" data-icon="inline-start" />
          {approveMutation.isPending ? "Merging..." : "Approve Merge"}
        </Button>

        <Button
          variant="outline"
          disabled={isBusy}
          onClick={() => rejectMutation.mutate(proposalId)}
        >
          <X className="h-4 w-4" data-icon="inline-start" />
          {rejectMutation.isPending ? "Rejecting..." : "Reject"}
        </Button>

        <Button
          variant="ghost"
          disabled={isBusy}
          onClick={() => advance()}
          className="ml-auto"
        >
          <SkipForward className="h-4 w-4" data-icon="inline-start" />
          Skip for Now
        </Button>
      </div>
    </div>
  );
}

function EmptyMergeState({ message }: { message: string }) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center gap-3 p-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
        <CheckCircle2 className="h-6 w-6 text-green-600 dark:text-green-400" />
      </div>
      <h3 className="text-lg font-medium">{message}</h3>
      <p className="text-sm text-muted-foreground">
        New merge proposals will appear here when similar entities are detected.
      </p>
    </div>
  );
}
