"use client";

import { Users, User, Lightbulb } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { DateGroup } from "@/components/nav/date-group";
import { EntityListItemRow } from "@/components/nav/entity-list-item";
import { useEntityList } from "@/hooks/use-entities";
import { useUIStore } from "@/stores/ui-store";
import type { EntityListItem } from "@/lib/types";

const TYPE_GROUPS = [
  { key: "partner", title: "Partners", icon: Users, groupId: "partners" },
  { key: "person", title: "People", icon: User, groupId: "people" },
  { key: "initiative", title: "Initiatives", icon: Lightbulb, groupId: "initiatives" },
] as const;

export function EntityList() {
  const entityTypeFilter = useUIStore((s) => s.entityTypeFilter);
  const entitySort = useUIStore((s) => s.entitySort);

  const { data: entities, isLoading } = useEntityList(
    entityTypeFilter,
    entitySort,
  );

  if (isLoading) {
    return <EntityListSkeleton />;
  }

  if (!entities || entities.length === 0) {
    return (
      <p className="px-3 py-4 text-xs text-muted-foreground">
        No entities found
      </p>
    );
  }

  // Group entities by type
  const grouped: Record<string, EntityListItem[]> = {};
  for (const entity of entities) {
    const type = entity.entity_type;
    if (!grouped[type]) grouped[type] = [];
    grouped[type].push(entity);
  }

  // Filter visible groups based on type filter
  const visibleGroups = entityTypeFilter
    ? TYPE_GROUPS.filter((g) => g.key === entityTypeFilter)
    : TYPE_GROUPS;

  return (
    <div>
      {visibleGroups.map((group) => {
        const items = grouped[group.key] ?? [];
        if (items.length === 0) return null;

        return (
          <DateGroup
            key={group.key}
            title={group.title}
            icon={group.icon}
            count={items.length}
            groupId={group.groupId}
          >
            {items.map((entity) => (
              <EntityListItemRow key={entity.entity_id} entity={entity} />
            ))}
          </DateGroup>
        );
      })}
    </div>
  );
}

function EntityListSkeleton() {
  return (
    <div className="space-y-2 px-3 py-2">
      <Skeleton className="h-4 w-16" />
      <Skeleton className="h-10 w-full rounded-md" />
      <Skeleton className="h-10 w-full rounded-md" />
      <Skeleton className="h-4 w-16 mt-2" />
      <Skeleton className="h-10 w-full rounded-md" />
      <Skeleton className="h-10 w-full rounded-md" />
    </div>
  );
}
