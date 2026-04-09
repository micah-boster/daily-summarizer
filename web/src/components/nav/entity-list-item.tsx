"use client";

import { differenceInDays, parseISO } from "date-fns";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/ui-store";
import type { EntityListItem } from "@/lib/types";

interface EntityListItemProps {
  entity: EntityListItem;
}

export function EntityListItemRow({ entity }: EntityListItemProps) {
  const selectedEntityId = useUIStore((s) => s.selectedEntityId);
  const selectEntity = useUIStore((s) => s.selectEntity);
  const setActiveTab = useUIStore((s) => s.setActiveTab);

  const isSelected = selectedEntityId === entity.entity_id;

  const isRecentlyActive =
    entity.last_active_date != null &&
    differenceInDays(new Date(), parseISO(entity.last_active_date)) <= 30;

  return (
    <button
      onClick={() => {
        selectEntity(entity.entity_id);
        setActiveTab("entities");
      }}
      data-kb-item
      className={cn(
        "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors",
        isSelected
          ? "bg-accent text-accent-foreground"
          : "hover:bg-accent/50",
      )}
    >
      {/* Activity dot */}
      {isRecentlyActive && (
        <span className="h-2 w-2 flex-shrink-0 rounded-full bg-green-500" />
      )}

      {/* Name */}
      <span className="flex-1 truncate font-medium">{entity.name}</span>

      {/* Mention count */}
      <span className="flex-shrink-0 text-xs text-muted-foreground">
        {entity.mention_count}
      </span>
    </button>
  );
}
