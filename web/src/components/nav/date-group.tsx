"use client";

import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useUIStore } from "@/stores/ui-store";

interface DateGroupProps {
  title: string;
  icon: LucideIcon;
  count: number;
  groupId: string;
  children: ReactNode;
}

export function DateGroup({
  title,
  icon: Icon,
  count,
  groupId,
  children,
}: DateGroupProps) {
  const expanded = useUIStore(
    (s) => s.expandedNavGroups[groupId] ?? true,
  );
  const toggle = useUIStore((s) => s.toggleNavGroup);

  return (
    <div>
      <button
        onClick={() => toggle(groupId)}
        className="flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-xs uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground"
      >
        <Icon className="h-3.5 w-3.5" />
        <span>{title}</span>
        <Badge variant="secondary" className="ml-0.5 text-[10px] px-1.5 py-0">
          {count}
        </Badge>
        <div className="flex-1" />
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5" />
        )}
      </button>

      {expanded && (
        <div className="flex flex-col gap-0.5 px-1 pb-2">{children}</div>
      )}
    </div>
  );
}
