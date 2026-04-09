"use client";

import { useEntityScopedView, useRelatedEntities } from "@/hooks/use-entities";
import { useUIStore } from "@/stores/ui-store";
import { Skeleton } from "@/components/ui/skeleton";

interface EntitySidebarProps {
  entityId: string;
}

export function EntitySidebar({ entityId }: EntitySidebarProps) {
  const { data: entityData, isLoading: entityLoading } =
    useEntityScopedView(entityId);
  const { data: related, isLoading: relatedLoading } =
    useRelatedEntities(entityId);
  const selectEntity = useUIStore((s) => s.selectEntity);

  if (entityLoading) {
    return <SidebarSkeleton />;
  }

  if (!entityData) {
    return (
      <p className="text-xs text-muted-foreground">
        No entity data available
      </p>
    );
  }

  return (
    <div className="space-y-5">
      {/* Entity type */}
      <MetadataSection title="Type">
        <span className="text-xs font-medium uppercase tracking-wider">
          {entityData.entity_type}
        </span>
      </MetadataSection>

      {/* Aliases */}
      {entityData.aliases.length > 0 && (
        <MetadataSection title="Aliases">
          <div className="flex flex-wrap gap-1.5">
            {entityData.aliases.map((alias) => (
              <span
                key={alias}
                className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
              >
                {alias}
              </span>
            ))}
          </div>
        </MetadataSection>
      )}

      {/* Stats */}
      <MetadataSection title="Overview">
        <div className="grid grid-cols-2 gap-2">
          <StatBox label="Mentions" value={entityData.total_mentions} />
          <StatBox
            label="Commitments"
            value={entityData.open_commitments.length}
          />
        </div>
      </MetadataSection>

      {/* Date range */}
      {(entityData.from_date || entityData.to_date) && (
        <MetadataSection title="Date Range">
          <p className="text-xs text-muted-foreground">
            {entityData.from_date ?? "?"} to {entityData.to_date ?? "?"}
          </p>
        </MetadataSection>
      )}

      {/* Related entities */}
      <MetadataSection title="Related Entities">
        {relatedLoading ? (
          <div className="space-y-1">
            <Skeleton className="h-6 w-full rounded-full" />
            <Skeleton className="h-6 w-3/4 rounded-full" />
          </div>
        ) : related && related.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {related.map((r) => (
              <button
                key={r.entity_id}
                onClick={() => selectEntity(r.entity_id)}
                className="rounded-full bg-muted px-2 py-1 text-xs cursor-pointer transition-colors hover:bg-accent"
              >
                {r.name}{" "}
                <span className="text-muted-foreground">
                  ({r.co_mention_count})
                </span>
              </button>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            No related entities found
          </p>
        )}
      </MetadataSection>
    </div>
  );
}

function MetadataSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
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

function SidebarSkeleton() {
  return (
    <div className="space-y-5">
      <div>
        <Skeleton className="mb-2 h-3 w-12" />
        <Skeleton className="h-4 w-20" />
      </div>
      <div>
        <Skeleton className="mb-2 h-3 w-16" />
        <Skeleton className="h-4 w-full" />
      </div>
      <div>
        <Skeleton className="mb-2 h-3 w-20" />
        <div className="grid grid-cols-2 gap-2">
          <Skeleton className="h-12 rounded-md" />
          <Skeleton className="h-12 rounded-md" />
        </div>
      </div>
    </div>
  );
}
