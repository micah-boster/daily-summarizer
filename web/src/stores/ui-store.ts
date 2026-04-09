import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface UIState {
  leftNavCollapsed: boolean;
  rightSidebarCollapsed: boolean;
  collapsedSections: Record<string, boolean>;
  expandedNavGroups: Record<string, boolean>;

  // Entity navigation state
  activeTab: "summaries" | "entities";
  selectedEntityId: string | null;
  entityTypeFilter: string | null;
  entitySort: "activity" | "name";

  toggleLeftNav: () => void;
  toggleRightSidebar: () => void;
  toggleSection: (id: string) => void;
  toggleNavGroup: (id: string) => void;

  // Entity navigation actions
  setActiveTab: (tab: "summaries" | "entities") => void;
  selectEntity: (id: string | null) => void;
  setEntityTypeFilter: (type: string | null) => void;
  setEntitySort: (sort: "activity" | "name") => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      leftNavCollapsed: false,
      rightSidebarCollapsed: false,
      collapsedSections: {},
      expandedNavGroups: {
        daily: true,
        weekly: true,
        monthly: true,
        partners: true,
        people: true,
        initiatives: true,
      },

      // Entity navigation defaults
      activeTab: "summaries",
      selectedEntityId: null,
      entityTypeFilter: null,
      entitySort: "activity",

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

      setActiveTab: (tab) => set({ activeTab: tab }),

      selectEntity: (id) => set({ selectedEntityId: id }),

      setEntityTypeFilter: (type) => set({ entityTypeFilter: type }),

      setEntitySort: (sort) => set({ entitySort: sort }),
    }),
    {
      name: "ui-state",
      storage: createJSONStorage(() => sessionStorage),
    },
  ),
);
