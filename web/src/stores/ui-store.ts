import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface UIState {
  leftNavCollapsed: boolean;
  rightSidebarCollapsed: boolean;
  collapsedSections: Record<string, boolean>;
  expandedNavGroups: Record<string, boolean>;

  toggleLeftNav: () => void;
  toggleRightSidebar: () => void;
  toggleSection: (id: string) => void;
  toggleNavGroup: (id: string) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      leftNavCollapsed: false,
      rightSidebarCollapsed: false,
      collapsedSections: {},
      expandedNavGroups: { daily: true, weekly: true, monthly: true },

      toggleLeftNav: () =>
        set((s) => ({ leftNavCollapsed: !s.leftNavCollapsed })),

      toggleRightSidebar: () =>
        set((s) => ({ rightSidebarCollapsed: !s.rightSidebarCollapsed })),

      toggleSection: (id: string) =>
        set((s) => ({
          collapsedSections: {
            ...s.collapsedSections,
            [id]: !s.collapsedSections[id],
          },
        })),

      toggleNavGroup: (id: string) =>
        set((s) => ({
          expandedNavGroups: {
            ...s.expandedNavGroups,
            [id]: !s.expandedNavGroups[id],
          },
        })),
    }),
    {
      name: "ui-state",
      storage: createJSONStorage(() => sessionStorage),
    },
  ),
);
