"use client";

import { AppShell } from "@/components/layout/app-shell";
import { LeftNav } from "@/components/layout/left-nav";
import { RightSidebar } from "@/components/layout/right-sidebar";
import { SidebarRail } from "@/components/layout/sidebar-rail";
import { useUIStore } from "@/stores/ui-store";

export default function Home() {
  const leftCollapsed = useUIStore((s) => s.leftNavCollapsed);
  const rightCollapsed = useUIStore((s) => s.rightSidebarCollapsed);
  const toggleLeftNav = useUIStore((s) => s.toggleLeftNav);
  const toggleRightSidebar = useUIStore((s) => s.toggleRightSidebar);

  return (
    <AppShell
      leftNav={
        leftCollapsed ? (
          <SidebarRail side="left" onExpand={toggleLeftNav} />
        ) : (
          <LeftNav onCollapse={toggleLeftNav}>
            <p className="p-4 text-sm text-muted-foreground">
              Date navigation coming soon
            </p>
          </LeftNav>
        )
      }
      rightSidebar={
        rightCollapsed ? (
          <SidebarRail side="right" onExpand={toggleRightSidebar} />
        ) : (
          <RightSidebar onCollapse={toggleRightSidebar}>
            <p className="p-4 text-sm text-muted-foreground">
              Summary metadata coming soon
            </p>
          </RightSidebar>
        )
      }
    >
      <div className="p-8">
        <h1 className="text-2xl font-semibold">Daily Summary</h1>
        <p className="mt-2 text-muted-foreground">
          Select a date from the left panel
        </p>
      </div>
    </AppShell>
  );
}
