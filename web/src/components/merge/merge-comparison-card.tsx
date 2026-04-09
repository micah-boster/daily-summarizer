"use client";

import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { EntityListItem } from "@/lib/types";

const TYPE_COLORS: Record<string, string> = {
  partner: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  person: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  initiative:
    "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
};

function scoreColor(score: number): string {
  if (score >= 0.9) return "text-green-600 dark:text-green-400";
  if (score >= 0.8) return "text-yellow-600 dark:text-yellow-400";
  return "text-orange-600 dark:text-orange-400";
}

interface MergeComparisonCardProps {
  entity: EntityListItem;
  aliases: string[];
  score: number;
  isSelected: boolean;
  onSelect: () => void;
  label?: string;
}

export function MergeComparisonCard({
  entity,
  aliases,
  score,
  isSelected,
  onSelect,
  label,
}: MergeComparisonCardProps) {
  return (
    <Card
      className={cn(
        "cursor-pointer transition-all",
        isSelected
          ? "ring-2 ring-primary bg-primary/5"
          : "hover:ring-1 hover:ring-foreground/20",
      )}
      onClick={onSelect}
    >
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-lg">{entity.name}</CardTitle>
          <Badge
            className={cn(
              "shrink-0 border-0",
              TYPE_COLORS[entity.entity_type] ?? "",
            )}
          >
            {entity.entity_type}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Aliases */}
        {aliases.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              Aliases
            </p>
            <div className="flex flex-wrap gap-1">
              {aliases.map((alias) => (
                <Badge key={alias} variant="outline" className="text-xs">
                  {alias}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Stats row */}
        <div className="flex items-center gap-4 text-sm">
          <div>
            <span className="font-semibold">{entity.mention_count}</span>{" "}
            <span className="text-muted-foreground">mentions</span>
          </div>
          <div className={cn("font-medium", scoreColor(score))}>
            {Math.round(score * 100)}% similar
          </div>
        </div>

        {/* Selection label */}
        {isSelected && (
          <p className="text-xs font-medium text-primary">
            Primary (name kept)
          </p>
        )}
        {label && !isSelected && (
          <p className="text-xs text-muted-foreground">{label}</p>
        )}
      </CardContent>
    </Card>
  );
}
