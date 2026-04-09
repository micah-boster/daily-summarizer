"use client";

import { useUIStore } from "@/stores/ui-store";
import { Button } from "@/components/ui/button";
import { PencilIcon, Trash2Icon } from "lucide-react";

interface EntityHeaderProps {
  name: string;
  entityType: string;
  entityId: string;
  aliases: string[];
}

export function EntityHeader({
  name,
  entityType,
  entityId,
  aliases,
}: EntityHeaderProps) {
  const openFormPanel = useUIStore((s) => s.openFormPanel);
  const openDeleteDialog = useUIStore((s) => s.openDeleteDialog);

  return (
    <div className="space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold tracking-tight">{name}</h1>
          <span className="inline-block rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {entityType}
          </span>
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => openFormPanel("edit", entityId)}
          >
            <PencilIcon data-icon="inline-start" className="size-3.5" />
            Edit
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => openDeleteDialog(entityId)}
          >
            <Trash2Icon data-icon="inline-start" className="size-3.5" />
            Delete
          </Button>
        </div>
      </div>
    </div>
  );
}
