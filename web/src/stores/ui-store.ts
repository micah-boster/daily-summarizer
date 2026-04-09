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

  // Entity form panel state
  formPanelOpen: boolean;
  formPanelMode: "create" | "edit";
  formPanelEntityId: string | null;

  // Entity delete dialog state
  deleteDialogOpen: boolean;
  deleteDialogEntityId: string | null;

  // Merge review state
  showMergeReview: boolean;

  // Date/view selection state (shared between page.tsx and command palette)
  selectedDate: string | null;
  selectedViewType: "daily" | "weekly" | "monthly";

  // Command palette state
  commandPaletteOpen: boolean;
  recentEntities: string[];
  recentDates: string[];

  toggleLeftNav: () => void;
  toggleRightSidebar: () => void;
  toggleSection: (id: string) => void;
  toggleNavGroup: (id: string) => void;

  // Entity navigation actions
  setActiveTab: (tab: "summaries" | "entities") => void;
  selectEntity: (id: string | null) => void;
  setEntityTypeFilter: (type: string | null) => void;
  setEntitySort: (sort: "activity" | "name") => void;

  // Entity form panel actions
  openFormPanel: (mode: "create" | "edit", entityId?: string | null) => void;
  closeFormPanel: () => void;

  // Entity delete dialog actions
  openDeleteDialog: (entityId: string) => void;
  closeDeleteDialog: () => void;

  // Merge review actions
  setShowMergeReview: (show: boolean) => void;

  // Date/view selection actions
  setSelectedDate: (date: string | null) => void;
  setSelectedViewType: (type: "daily" | "weekly" | "monthly") => void;

  // Command palette actions
  toggleCommandPalette: () => void;
  setCommandPaletteOpen: (open: boolean) => void;
  addRecentEntity: (entityId: string) => void;
  addRecentDate: (date: string) => void;
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

      // Entity form panel defaults
      formPanelOpen: false,
      formPanelMode: "create",
      formPanelEntityId: null,

      // Entity delete dialog defaults
      deleteDialogOpen: false,
      deleteDialogEntityId: null,

      // Merge review defaults
      showMergeReview: false,

      // Date/view selection defaults
      selectedDate: null,
      selectedViewType: "daily",

      // Command palette defaults
      commandPaletteOpen: false,
      recentEntities: [],
      recentDates: [],

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

      selectEntity: (id) =>
        set((s) => ({
          selectedEntityId: id,
          recentEntities: id
            ? [id, ...s.recentEntities.filter((e) => e !== id)].slice(0, 5)
            : s.recentEntities,
        })),

      setEntityTypeFilter: (type) => set({ entityTypeFilter: type }),

      setEntitySort: (sort) => set({ entitySort: sort }),

      // Entity form panel actions
      openFormPanel: (mode, entityId = null) =>
        set({
          formPanelOpen: true,
          formPanelMode: mode,
          formPanelEntityId: entityId ?? null,
        }),

      closeFormPanel: () =>
        set({
          formPanelOpen: false,
          formPanelEntityId: null,
        }),

      // Entity delete dialog actions
      openDeleteDialog: (entityId) =>
        set({
          deleteDialogOpen: true,
          deleteDialogEntityId: entityId,
        }),

      closeDeleteDialog: () =>
        set({
          deleteDialogOpen: false,
          deleteDialogEntityId: null,
        }),

      // Merge review actions
      setShowMergeReview: (show) =>
        set({
          showMergeReview: show,
          ...(show ? { selectedEntityId: null } : {}),
        }),

      // Date/view selection actions
      setSelectedDate: (date) => set({ selectedDate: date }),
      setSelectedViewType: (type) => set({ selectedViewType: type }),

      // Command palette actions
      toggleCommandPalette: () =>
        set((s) => ({ commandPaletteOpen: !s.commandPaletteOpen })),

      setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),

      addRecentEntity: (entityId) =>
        set((s) => ({
          recentEntities: [
            entityId,
            ...s.recentEntities.filter((e) => e !== entityId),
          ].slice(0, 5),
        })),

      addRecentDate: (date) =>
        set((s) => ({
          recentDates: [
            date,
            ...s.recentDates.filter((d) => d !== date),
          ].slice(0, 5),
        })),
    }),
    {
      name: "ui-state",
      storage: createJSONStorage(() => sessionStorage),
    },
  ),
);
