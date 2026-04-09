"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { Badge } from "@/components/ui/badge";
import { useUIStore } from "@/stores/ui-store";
import { useEntityList } from "@/hooks/use-entities";
import {
  CalendarIcon,
  UserIcon,
  BuildingIcon,
  ZapIcon,
  ClockIcon,
  BriefcaseIcon,
} from "lucide-react";
import type { EntityListItem } from "@/lib/types";

/* ------------------------------------------------------------------ */
/*  Date parsing helpers                                               */
/* ------------------------------------------------------------------ */

function parseNaturalDate(input: string): Date | null {
  const trimmed = input.trim().toLowerCase();
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  if (trimmed === "today") return today;

  if (trimmed === "yesterday") {
    const d = new Date(today);
    d.setDate(d.getDate() - 1);
    return d;
  }

  const daysOfWeek = [
    "sunday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
  ];
  const lastMatch = trimmed.match(/^last\s+(\w+)$/);
  if (lastMatch) {
    const dayIdx = daysOfWeek.indexOf(lastMatch[1]);
    if (dayIdx >= 0) {
      const d = new Date(today);
      const currentDay = d.getDay();
      const diff = ((currentDay - dayIdx + 7) % 7) || 7;
      d.setDate(d.getDate() - diff);
      return d;
    }
  }

  // ISO format: 2026-04-08
  const isoMatch = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    const d = new Date(
      parseInt(isoMatch[1]),
      parseInt(isoMatch[2]) - 1,
      parseInt(isoMatch[3]),
    );
    if (!isNaN(d.getTime())) return d;
  }

  // Month Day format: April 8, Apr 8
  const months: Record<string, number> = {
    january: 0,
    february: 1,
    march: 2,
    april: 3,
    may: 4,
    june: 5,
    july: 6,
    august: 7,
    september: 8,
    october: 9,
    november: 10,
    december: 11,
    jan: 0,
    feb: 1,
    mar: 2,
    apr: 3,
    jun: 5,
    jul: 6,
    aug: 7,
    sep: 8,
    oct: 9,
    nov: 10,
    dec: 11,
  };

  const monthDayMatch = trimmed.match(/^(\w+)\s+(\d{1,2})(?:,?\s*(\d{4}))?$/);
  if (monthDayMatch) {
    const monthIdx = months[monthDayMatch[1]];
    if (monthIdx !== undefined) {
      const year = monthDayMatch[3]
        ? parseInt(monthDayMatch[3])
        : today.getFullYear();
      const d = new Date(year, monthIdx, parseInt(monthDayMatch[2]));
      if (!isNaN(d.getTime())) return d;
    }
  }

  return null;
}

function formatDate(date: Date): string {
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function toISODate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/* ------------------------------------------------------------------ */
/*  Entity type icon helper                                            */
/* ------------------------------------------------------------------ */

function EntityTypeIcon({ type }: { type: string }) {
  switch (type) {
    case "person":
      return <UserIcon className="size-4 text-muted-foreground" />;
    case "partner":
      return <BuildingIcon className="size-4 text-muted-foreground" />;
    case "initiative":
      return <BriefcaseIcon className="size-4 text-muted-foreground" />;
    default:
      return <UserIcon className="size-4 text-muted-foreground" />;
  }
}

/* ------------------------------------------------------------------ */
/*  Command Palette                                                    */
/* ------------------------------------------------------------------ */

export function CommandPalette() {
  const open = useUIStore((s) => s.commandPaletteOpen);
  const setOpen = useUIStore((s) => s.setCommandPaletteOpen);
  const recentEntityIds = useUIStore((s) => s.recentEntities);
  const recentDates = useUIStore((s) => s.recentDates);
  const selectEntity = useUIStore((s) => s.selectEntity);
  const setActiveTab = useUIStore((s) => s.setActiveTab);
  const openFormPanel = useUIStore((s) => s.openFormPanel);
  const setShowMergeReview = useUIStore((s) => s.setShowMergeReview);
  const addRecentDate = useUIStore((s) => s.addRecentDate);
  const setSelectedDate = useUIStore((s) => s.setSelectedDate);
  const setSelectedViewType = useUIStore((s) => s.setSelectedViewType);

  const [search, setSearch] = useState("");

  // Fetch entities (uses TanStack Query cache)
  const { data: entities = [] } = useEntityList();

  // Global keyboard shortcut
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (
        (e.metaKey || e.ctrlKey) &&
        e.key === "k" &&
        !(
          e.target instanceof HTMLTextAreaElement ||
          (e.target instanceof HTMLElement && e.target.isContentEditable)
        )
      ) {
        e.preventDefault();
        setOpen(!open);
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, setOpen]);

  // Reset search when closed
  useEffect(() => {
    if (!open) setSearch("");
  }, [open]);

  // Determine prefix filter mode
  const prefixMode = useMemo(() => {
    if (search.startsWith("/")) return "actions" as const;
    if (search.startsWith("@")) return "entities" as const;
    if (search.startsWith("#")) return "dates" as const;
    return null;
  }, [search]);

  // Strip prefix for matching
  const searchQuery = useMemo(() => {
    if (prefixMode) return search.slice(1).trim();
    return search.trim();
  }, [search, prefixMode]);

  const isEmpty = searchQuery.length === 0;

  // Build entity map for recent lookups
  const entityMap = useMemo(() => {
    const map = new Map<string, EntityListItem>();
    for (const e of entities) map.set(e.entity_id, e);
    return map;
  }, [entities]);

  // Recent entities resolved from IDs
  const recentEntitiesResolved = useMemo(
    () =>
      recentEntityIds
        .map((id) => entityMap.get(id))
        .filter(Boolean) as EntityListItem[],
    [recentEntityIds, entityMap],
  );

  // Sort entities with recency boost
  const sortedEntities = useMemo(() => {
    const recentSet = new Set(recentEntityIds);
    return [...entities].sort((a, b) => {
      const aRecent = recentSet.has(a.entity_id) ? 0 : 1;
      const bRecent = recentSet.has(b.entity_id) ? 0 : 1;
      if (aRecent !== bRecent) return aRecent - bRecent;
      return b.mention_count - a.mention_count;
    });
  }, [entities, recentEntityIds]);

  // Parse date from search
  const parsedDate = useMemo(() => {
    if (!searchQuery) return null;
    return parseNaturalDate(searchQuery);
  }, [searchQuery]);

  // Handlers
  const handleSelectEntity = useCallback(
    (entityId: string) => {
      setOpen(false);
      setActiveTab("entities");
      selectEntity(entityId);
    },
    [setOpen, setActiveTab, selectEntity],
  );

  const handleSelectDate = useCallback(
    (dateStr: string) => {
      setOpen(false);
      addRecentDate(dateStr);
      setActiveTab("summaries");
      setSelectedDate(dateStr);
      setSelectedViewType("daily");
    },
    [setOpen, addRecentDate, setActiveTab, setSelectedDate, setSelectedViewType],
  );

  const handleCreateEntity = useCallback(() => {
    setOpen(false);
    openFormPanel("create");
  }, [setOpen, openFormPanel]);

  const handleMergeReview = useCallback(() => {
    setOpen(false);
    setActiveTab("entities");
    setShowMergeReview(true);
  }, [setOpen, setActiveTab, setShowMergeReview]);

  // Static actions
  const actions = [
    {
      id: "create-entity",
      label: "Create Entity",
      description: "Open the entity creation form",
      onSelect: handleCreateEntity,
    },
    {
      id: "review-merges",
      label: "Review Merge Proposals",
      description: "Navigate to merge review queue",
      onSelect: handleMergeReview,
    },
  ];

  const showEntities = !prefixMode || prefixMode === "entities";
  const showDates = !prefixMode || prefixMode === "dates";
  const showActions = !prefixMode || prefixMode === "actions";

  return (
    <CommandDialog
      open={open}
      onOpenChange={setOpen}
      title="Command Palette"
      description="Search entities, dates, or actions"
      className="sm:max-w-[640px]"
    >
      <Command shouldFilter={!prefixMode} loop>
        <CommandInput
          placeholder="Search entities, dates, or actions..."
          value={search}
          onValueChange={setSearch}
        />
        <CommandList className="max-h-80">
          <CommandEmpty>
            {isEmpty ? (
              <span className="text-muted-foreground">
                Start typing to search entities, dates, or actions...
              </span>
            ) : (
              "No results found."
            )}
          </CommandEmpty>

          {/* ---- Empty state: show recents ---- */}
          {isEmpty && !prefixMode && (
            <>
              {recentEntitiesResolved.length > 0 && (
                <CommandGroup heading="Recent Entities">
                  {recentEntitiesResolved.map((entity) => (
                    <CommandItem
                      key={entity.entity_id}
                      value={`recent-entity-${entity.entity_id}`}
                      onSelect={() => handleSelectEntity(entity.entity_id)}
                    >
                      <ClockIcon className="size-4 text-muted-foreground" />
                      <span>{entity.name}</span>
                      <Badge variant="secondary" className="ml-auto text-[10px]">
                        {entity.entity_type}
                      </Badge>
                    </CommandItem>
                  ))}
                </CommandGroup>
              )}

              {recentDates.length > 0 && (
                <CommandGroup heading="Recent Dates">
                  {recentDates.map((dateStr) => {
                    const d = new Date(dateStr + "T00:00:00");
                    return (
                      <CommandItem
                        key={dateStr}
                        value={`recent-date-${dateStr}`}
                        onSelect={() => handleSelectDate(dateStr)}
                      >
                        <ClockIcon className="size-4 text-muted-foreground" />
                        <span>{formatDate(d)}</span>
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
              )}
            </>
          )}

          {/* ---- Entities group ---- */}
          {!isEmpty && showEntities && (
            <CommandGroup heading="Entities">
              {sortedEntities.map((entity) => (
                <CommandItem
                  key={entity.entity_id}
                  value={entity.name}
                  onSelect={() => handleSelectEntity(entity.entity_id)}
                >
                  <EntityTypeIcon type={entity.entity_type} />
                  <span>{entity.name}</span>
                  <span className="ml-auto flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      {entity.mention_count} mentions
                    </span>
                    <Badge variant="secondary" className="text-[10px]">
                      {entity.entity_type}
                    </Badge>
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          )}

          {/* ---- Dates group ---- */}
          {!isEmpty && showDates && parsedDate && (
            <>
              {showEntities && <CommandSeparator />}
              <CommandGroup heading="Dates">
                <CommandItem
                  value={`date-${toISODate(parsedDate)}`}
                  onSelect={() => handleSelectDate(toISODate(parsedDate))}
                >
                  <CalendarIcon className="size-4 text-muted-foreground" />
                  <span>{formatDate(parsedDate)}</span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    View summary
                  </span>
                </CommandItem>
              </CommandGroup>
            </>
          )}

          {/* ---- Actions group ---- */}
          {showActions && (
            <>
              {(showEntities || showDates) && !isEmpty && <CommandSeparator />}
              <CommandGroup heading="Actions">
                {actions.map((action) => (
                  <CommandItem
                    key={action.id}
                    value={action.label}
                    onSelect={action.onSelect}
                  >
                    <ZapIcon className="size-4 text-muted-foreground" />
                    <span>{action.label}</span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {action.description}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          )}
        </CommandList>

        {/* ---- Footer with keyboard hints ---- */}
        <div className="flex items-center justify-center gap-4 border-t px-3 py-2 text-[11px] text-muted-foreground">
          <span>
            <kbd className="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">
              &uarr;&darr;
            </kbd>{" "}
            Navigate
          </span>
          <span>
            <kbd className="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">
              &crarr;
            </kbd>{" "}
            Select
          </span>
          <span>
            <kbd className="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">
              esc
            </kbd>{" "}
            Close
          </span>
          <span className="ml-2 border-l pl-2">
            <kbd className="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">
              @
            </kbd>{" "}
            entities{" "}
            <kbd className="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">
              #
            </kbd>{" "}
            dates{" "}
            <kbd className="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">
              /
            </kbd>{" "}
            actions
          </span>
        </div>
      </Command>
    </CommandDialog>
  );
}
