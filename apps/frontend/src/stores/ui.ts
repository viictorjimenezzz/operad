import { create } from "zustand";
import { persist } from "zustand/middleware";

export type EventKindFilter = "all" | "agent" | "algo" | "error";

export type GraphSelection =
  | { kind: "node"; nodeKey: string }
  | { kind: "edge"; agentPath: string }
  | { kind: "group"; compositePath: string }
  | null;

export type GraphInspectorTab =
  | "overview"
  | "invocations"
  | "prompts"
  | "events"
  | "experiment"
  | "langfuse"
  | "fields";

const SPLIT_MIN = 320;
const SPLIT_DEFAULT = 0.5; // fraction of viewport

export function clampSplitFraction(fraction: number): number {
  if (!Number.isFinite(fraction)) return SPLIT_DEFAULT;
  return Math.max(0.25, Math.min(0.75, fraction));
}

export function clampSplitWidth(
  px: number,
  viewportWidth = typeof window === "undefined" ? 1200 : window.innerWidth,
): number {
  const max = Math.max(SPLIT_MIN, viewportWidth - SPLIT_MIN);
  return Math.max(SPLIT_MIN, Math.min(max, Math.round(px)));
}

interface UIState {
  currentTab: string;
  eventKindFilter: EventKindFilter;
  eventSearch: string;
  autoFollow: boolean;
  eventsFollow: boolean;
  sidebarCollapsed: boolean;
  selectedInvocationId: string | null;
  selectedInvocationAgentPath: string | null;
  comparisonInvocationId: string | null;
  comparisonInvocationAgentPath: string | null;
  graphSelection: GraphSelection;
  graphInspectorTab: GraphInspectorTab;
  /** Inspector pane width as a fraction of viewport (0.25–0.75). */
  graphSplitFraction: number;
  setCurrentTab: (tab: string) => void;
  setEventKindFilter: (f: EventKindFilter) => void;
  setEventSearch: (s: string) => void;
  setAutoFollow: (v: boolean) => void;
  setEventsFollow: (v: boolean) => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (v: boolean) => void;
  setSelectedInvocation: (invocationId: string, agentPath: string) => void;
  clearSelectedInvocation: () => void;
  setComparisonInvocation: (invocationId: string, agentPath: string) => void;
  clearComparisonInvocation: () => void;
  setGraphSelection: (selection: GraphSelection) => void;
  clearGraphSelection: () => void;
  setGraphInspectorTab: (tab: GraphInspectorTab) => void;
  setGraphSplitFraction: (f: number) => void;
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
      selectedInvocationId: null,
      selectedInvocationAgentPath: null,
      comparisonInvocationId: null,
      comparisonInvocationAgentPath: null,
      graphSelection: null,
      graphInspectorTab: "overview",
      graphSplitFraction: SPLIT_DEFAULT,
      setCurrentTab: (tab) => set({ currentTab: tab }),
      setEventKindFilter: (f) => set({ eventKindFilter: f }),
      setEventSearch: (s) => set({ eventSearch: s }),
      setAutoFollow: (v) => set({ autoFollow: v }),
      setEventsFollow: (v) => set({ eventsFollow: v }),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
      setSelectedInvocation: (invocationId, agentPath) =>
        set({ selectedInvocationId: invocationId, selectedInvocationAgentPath: agentPath }),
      clearSelectedInvocation: () =>
        set({ selectedInvocationId: null, selectedInvocationAgentPath: null }),
      setComparisonInvocation: (invocationId, agentPath) =>
        set({ comparisonInvocationId: invocationId, comparisonInvocationAgentPath: agentPath }),
      clearComparisonInvocation: () =>
        set({ comparisonInvocationId: null, comparisonInvocationAgentPath: null }),
      setGraphSelection: (selection) =>
        set((s) => {
          // Selecting a different leaf-edge resets the inspector tab to overview;
          // selecting a type node forces the fields tab; switching back keeps the
          // last tab the user was on.
          if (selection?.kind === "node")
            return { graphSelection: selection, graphInspectorTab: "fields" };
          if (selection?.kind === "edge" && s.graphInspectorTab === "fields")
            return { graphSelection: selection, graphInspectorTab: "overview" };
          return { graphSelection: selection };
        }),
      clearGraphSelection: () => set({ graphSelection: null }),
      setGraphInspectorTab: (tab) => set({ graphInspectorTab: tab }),
      setGraphSplitFraction: (f) => set({ graphSplitFraction: clampSplitFraction(f) }),
    }),
    {
      name: "operad.ui",
      partialize: (s) => ({
        eventKindFilter: s.eventKindFilter,
        autoFollow: s.autoFollow,
        eventsFollow: s.eventsFollow,
        sidebarCollapsed: s.sidebarCollapsed,
        graphSplitFraction: s.graphSplitFraction,
      }),
    },
  ),
);
