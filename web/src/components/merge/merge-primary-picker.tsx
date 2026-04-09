"use client";

import { cn } from "@/lib/utils";
import { MergeComparisonCard } from "./merge-comparison-card";
import type { EntityListItem } from "@/lib/types";

function scoreColor(score: number): string {
  if (score >= 0.9) return "text-green-600 dark:text-green-400";
  if (score >= 0.8) return "text-yellow-600 dark:text-yellow-400";
  return "text-orange-600 dark:text-orange-400";
}

interface MergePrimaryPickerProps {
  sourceEntity: EntityListItem;
  targetEntity: EntityListItem;
  sourceAliases: string[];
  targetAliases: string[];
  score: number;
  selectedPrimaryId: string | null;
  onSelectPrimary: (entityId: string) => void;
}

export function MergePrimaryPicker({
  sourceEntity,
  targetEntity,
  sourceAliases,
  targetAliases,
  score,
  selectedPrimaryId,
  onSelectPrimary,
}: MergePrimaryPickerProps) {
  const sourceSelected = selectedPrimaryId === sourceEntity.entity_id;
  const targetSelected = selectedPrimaryId === targetEntity.entity_id;

  return (
    <div className="space-y-3">
      <div className="flex items-stretch gap-3">
        {/* Source card */}
        <div className="flex-1 min-w-0">
          <MergeComparisonCard
            entity={sourceEntity}
            aliases={sourceAliases}
            score={score}
            isSelected={sourceSelected}
            onSelect={() => onSelectPrimary(sourceEntity.entity_id)}
            label={targetSelected ? "Will become alias" : undefined}
          />
        </div>

        {/* Center divider */}
        <div className="flex flex-col items-center justify-center gap-1 shrink-0">
          <div
            className={cn(
              "rounded-full px-2.5 py-1 text-xs font-semibold",
              scoreColor(score),
              "bg-muted",
            )}
          >
            {Math.round(score * 100)}%
          </div>
          <span className="text-xs text-muted-foreground">vs</span>
        </div>

        {/* Target card */}
        <div className="flex-1 min-w-0">
          <MergeComparisonCard
            entity={targetEntity}
            aliases={targetAliases}
            score={score}
            isSelected={targetSelected}
            onSelect={() => onSelectPrimary(targetEntity.entity_id)}
            label={sourceSelected ? "Will become alias" : undefined}
          />
        </div>
      </div>

      {/* Instruction text */}
      {!selectedPrimaryId && (
        <p className="text-center text-sm text-muted-foreground">
          Select which entity name to keep as primary
        </p>
      )}
    </div>
  );
}
