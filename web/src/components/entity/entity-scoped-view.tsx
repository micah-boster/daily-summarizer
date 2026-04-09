"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { useEntityScopedView } from "@/hooks/use-entities";
import { EntityHeader } from "./entity-header";
import { AliasChipList } from "./alias-chip-list";
import { AliasInput } from "./alias-input";
import { HighlightsSection } from "./highlights-section";
import { CommitmentsSection } from "./commitments-section";
import { ActivityTimeline } from "./activity-timeline";
import { Separator } from "@/components/ui/separator";

interface EntityScopedViewProps {
  entityId: string;
  onViewInSummary?: (date: string) => void;
}

export function EntityScopedView({
  entityId,
  onViewInSummary,
}: EntityScopedViewProps) {
  const { data, isLoading, isError } = useEntityScopedView(entityId);

  if (isLoading) {
    return <EntityViewSkeleton />;
  }

  if (isError || !data) {
    return (
      <div className="flex items-center justify-center p-8">
        <p className="text-sm text-muted-foreground">
          Failed to load entity details
        </p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <EntityHeader
        name={data.entity_name}
        entityType={data.entity_type}
        entityId={data.entity_id}
        aliases={data.aliases}
      />

      <div className="space-y-2">
        <AliasChipList aliases={data.aliases} entityId={data.entity_id} />
        <AliasInput
          entityId={data.entity_id}
          existingAliases={data.aliases}
        />
      </div>

      <Separator />

      <HighlightsSection
        totalMentions={data.total_mentions}
        activityByDate={data.activity_by_date}
        highlights={data.highlights}
      />

      <Separator />

      <CommitmentsSection commitments={data.open_commitments} />

      <Separator />

      <ActivityTimeline
        activityByDate={data.activity_by_date}
        onViewInSummary={onViewInSummary}
      />
    </div>
  );
}

function EntityViewSkeleton() {
  return (
    <div className="space-y-4 p-6">
      <Skeleton className="h-8 w-1/3" />
      <Skeleton className="h-4 w-20" />
      <div className="grid grid-cols-3 gap-2 pt-4">
        <Skeleton className="h-12 rounded-md" />
        <Skeleton className="h-12 rounded-md" />
        <Skeleton className="h-12 rounded-md" />
      </div>
      <Skeleton className="h-px w-full mt-4" />
      <Skeleton className="h-4 w-24 mt-4" />
      <Skeleton className="h-16 w-full rounded-md" />
      <Skeleton className="h-16 w-full rounded-md" />
      <Skeleton className="h-px w-full mt-4" />
      <Skeleton className="h-4 w-32 mt-4" />
      <Skeleton className="h-10 w-full rounded-md" />
      <Skeleton className="h-10 w-full rounded-md" />
      <Skeleton className="h-10 w-full rounded-md" />
    </div>
  );
}
