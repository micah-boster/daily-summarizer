"use client";

import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/ui-store";

const tabs = [
  { key: "summaries" as const, label: "Summaries" },
  { key: "entities" as const, label: "Entities" },
];

export function NavTabSwitcher() {
  const activeTab = useUIStore((s) => s.activeTab);
  const setActiveTab = useUIStore((s) => s.setActiveTab);

  return (
    <div className="flex border-b px-3 py-2">
      <div className="flex w-full rounded-md border bg-muted/50 p-0.5">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "flex-1 rounded-sm px-3 py-1 text-xs font-medium transition-colors",
              activeTab === tab.key
                ? "bg-accent text-accent-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  );
}
