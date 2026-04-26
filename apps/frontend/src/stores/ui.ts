import { create } from "zustand";
import { persist } from "zustand/middleware";

export type EventKindFilter = "all" | "agent" | "algo" | "error";
export type DrawerKind =
  | "langfuse"
  | "events"
  | "prompts"
  | "values"
  | "find-runs"
  | "experiment"
  | "diff"
  | "gradients"
  | null;
export type DrawerPayload = {
  agentPath?: string;
  attr?: string;
  side?: "in" | "out";
  invocationId?: string;
  fromInvocationId?: string;
  toInvocationId?: string;
  paramPath?: string;
  mode?: string;
  panel?: string;
  filter?: string;
  sort?: "time" | "frequency" | "length";
  [k: string]: unknown;
};

const DRAWER_MIN_WIDTH = 320;
const DRAWER_DEFAULT_WIDTH = 480;

export function clampDrawerWidth(
  px: number,
  viewportWidth = typeof window === "undefined" ? 1200 : window.innerWidth,
): number {
  const max = Math.max(DRAWER_MIN_WIDTH, Math.floor(viewportWidth * 0.6));
  return Math.max(DRAWER_MIN_WIDTH, Math.min(max, Math.round(px)));
}

interface UIState {
  currentTab: string;
  eventKindFilter: EventKindFilter;
  eventSearch: string;
  autoFollow: boolean;
  eventsFollow: boolean;
  sidebarCollapsed: boolean;
  drawer: { kind: Exclude<DrawerKind, null>; payload: DrawerPayload } | null;
  drawerWidth: number;
  selectedInvocationId: string | null;
  selectedInvocationAgentPath: string | null;
  comparisonInvocationId: string | null;
  comparisonInvocationAgentPath: string | null;
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
  setSelectedInvocation: (invocationId: string, agentPath: string) => void;
  clearSelectedInvocation: () => void;
  setComparisonInvocation: (invocationId: string, agentPath: string) => void;
  clearComparisonInvocation: () => void;
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
      drawerWidth: DRAWER_DEFAULT_WIDTH,
      selectedInvocationId: null,
      selectedInvocationAgentPath: null,
      comparisonInvocationId: null,
      comparisonInvocationAgentPath: null,
      setCurrentTab: (tab) => set({ currentTab: tab }),
      setEventKindFilter: (f) => set({ eventKindFilter: f }),
      setEventSearch: (s) => set({ eventSearch: s }),
      setAutoFollow: (v) => set({ autoFollow: v }),
      setEventsFollow: (v) => set({ eventsFollow: v }),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
      openDrawer: (kind, payload = {}) => set({ drawer: { kind, payload } }),
      closeDrawer: () => set({ drawer: null }),
      setDrawerWidth: (px) => set({ drawerWidth: clampDrawerWidth(px) }),
      setSelectedInvocation: (invocationId, agentPath) =>
        set({ selectedInvocationId: invocationId, selectedInvocationAgentPath: agentPath }),
      clearSelectedInvocation: () =>
        set({ selectedInvocationId: null, selectedInvocationAgentPath: null }),
      setComparisonInvocation: (invocationId, agentPath) =>
        set({ comparisonInvocationId: invocationId, comparisonInvocationAgentPath: agentPath }),
      clearComparisonInvocation: () =>
        set({ comparisonInvocationId: null, comparisonInvocationAgentPath: null }),
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
