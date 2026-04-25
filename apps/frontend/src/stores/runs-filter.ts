import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type RunStatusFilter = "all" | "running" | "ended" | "errors";
export type RunTimeFilter = "all" | "1h" | "24h" | "7d";

interface RunsFilterState {
  search: string;
  statusFilter: RunStatusFilter;
  timeFilter: RunTimeFilter;
  showSynthetic: boolean;
  setSearch: (s: string) => void;
  setStatusFilter: (f: RunStatusFilter) => void;
  setTimeFilter: (f: RunTimeFilter) => void;
  setShowSynthetic: (v: boolean) => void;
}

export const useRunsFilterStore = create<RunsFilterState>()(
  persist(
    (set) => ({
      search: "",
      statusFilter: "all",
      timeFilter: "all",
      showSynthetic: false,
      setSearch: (s) => set({ search: s }),
      setStatusFilter: (f) => set({ statusFilter: f }),
      setTimeFilter: (f) => set({ timeFilter: f }),
      setShowSynthetic: (v) => set({ showSynthetic: v }),
    }),
    {
      name: "operad.runs-filter",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (s) => ({
        statusFilter: s.statusFilter,
        timeFilter: s.timeFilter,
        showSynthetic: s.showSynthetic,
      }),
    },
  ),
);
