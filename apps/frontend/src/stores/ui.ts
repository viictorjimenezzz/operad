import { create } from "zustand";
import { persist } from "zustand/middleware";

export type EventKindFilter = "all" | "agent" | "algo" | "error";
export type DrawerKind = "langfuse" | "events" | "prompts" | "values" | null;
export type DrawerPayload = {
  agentPath?: string;
  attr?: string;
  side?: "in" | "out";
  [k: string]: unknown;
};

interface UIState {
  currentTab: string;
  eventKindFilter: EventKindFilter;
  eventSearch: string;
  autoFollow: boolean;
  eventsFollow: boolean;
  sidebarCollapsed: boolean;
  drawer: { kind: DrawerKind; payload: DrawerPayload } | null;
  drawerWidth: number;
  setCurrentTab: (tab: string) => void;
  setEventKindFilter: (f: EventKindFilter) => void;
  setEventSearch: (s: string) => void;
  setAutoFollow: (v: boolean) => void;
  setEventsFollow: (v: boolean) => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (v: boolean) => void;
  openDrawer: (kind: Exclude<DrawerKind, null>, payload?: DrawerPayload) => void;
  closeDrawer: () => void;
  setDrawerWidth: (px: number) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      currentTab: "overview",
      eventKindFilter: "all",
      eventSearch: "",
      autoFollow: true,
      eventsFollow: true,
      sidebarCollapsed: false,
      drawer: null,
      drawerWidth: 420,
      setCurrentTab: (tab) => set({ currentTab: tab }),
      setEventKindFilter: (f) => set({ eventKindFilter: f }),
      setEventSearch: (s) => set({ eventSearch: s }),
      setAutoFollow: (v) => set({ autoFollow: v }),
      setEventsFollow: (v) => set({ eventsFollow: v }),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
      openDrawer: (kind, payload = {}) => set({ drawer: { kind, payload } }),
      closeDrawer: () => set({ drawer: null }),
      setDrawerWidth: (px) => set({ drawerWidth: Math.max(280, Math.min(720, Math.round(px))) }),
    }),
    {
      name: "operad.ui",
      partialize: (s) => ({
        eventKindFilter: s.eventKindFilter,
        autoFollow: s.autoFollow,
        eventsFollow: s.eventsFollow,
        sidebarCollapsed: s.sidebarCollapsed,
        drawerWidth: s.drawerWidth,
      }),
    },
  ),
);
