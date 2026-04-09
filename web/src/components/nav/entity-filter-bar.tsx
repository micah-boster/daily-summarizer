"use client";

import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/ui-store";

const typeFilters = [
  { key: null, label: "All" },
  { key: "partner", label: "Partners" },
  { key: "person", label: "People" },
  { key: "initiative", label: "Initiatives" },
] as const;

const sortOptions = [
  { key: "activity" as const, label: "Activity" },
  { key: "name" as const, label: "Name" },
];

export function EntityFilterBar() {
  const entityTypeFilter = useUIStore((s) => s.entityTypeFilter);
  const setEntityTypeFilter = useUIStore((s) => s.setEntityTypeFilter);
  const entitySort = useUIStore((s) => s.entitySort);
  const setEntitySort = useUIStore((s) => s.setEntitySort);

  return (
    <div className="flex flex-col gap-1.5 border-b px-3 py-2">
      {/* Sort toggle */}
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          Sort:
        </span>
        {sortOptions.map((opt) => (
          <button
            key={opt.key}
            onClick={() => setEntitySort(opt.key)}
            className={cn(
              "rounded-sm px-2 py-0.5 text-[10px] font-medium transition-colors",
              entitySort === opt.key
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Type filter chips */}
      <div className="flex flex-wrap gap-1">
        {typeFilters.map((filter) => (
          <button
            key={filter.key ?? "all"}
            onClick={() => setEntityTypeFilter(filter.key ?? null)}
            className={cn(
              "rounded-full px-2 py-0.5 text-[10px] font-medium transition-colors",
              entityTypeFilter === filter.key
                ? "bg-accent text-accent-foreground"
                : "bg-muted/50 text-muted-foreground hover:text-foreground",
            )}
          >
            {filter.label}
          </button>
        ))}
      </div>
    </div>
  );
}
