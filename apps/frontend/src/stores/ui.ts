import { create } from "zustand";
import { persist } from "zustand/middleware";

export type RunListFilter = "all" | "algorithms" | "agents";
export type EventKindFilter = "all" | "agent" | "algo" | "error";

interface UIState {
  currentTab: string;
  runListFilter: RunListFilter;
  eventKindFilter: EventKindFilter;
  eventSearch: string;
  autoFollow: boolean;
  eventsFollow: boolean;
  setCurrentTab: (tab: string) => void;
  setRunListFilter: (f: RunListFilter) => void;
  setEventKindFilter: (f: EventKindFilter) => void;
  setEventSearch: (s: string) => void;
  setAutoFollow: (v: boolean) => void;
  setEventsFollow: (v: boolean) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      currentTab: "overview",
      runListFilter: "all",
      eventKindFilter: "all",
      eventSearch: "",
      autoFollow: true,
      eventsFollow: true,
      setCurrentTab: (tab) => set({ currentTab: tab }),
      setRunListFilter: (f) => set({ runListFilter: f }),
      setEventKindFilter: (f) => set({ eventKindFilter: f }),
      setEventSearch: (s) => set({ eventSearch: s }),
      setAutoFollow: (v) => set({ autoFollow: v }),
      setEventsFollow: (v) => set({ eventsFollow: v }),
    }),
    {
      name: "operad.ui",
      partialize: (s) => ({
        runListFilter: s.runListFilter,
        eventKindFilter: s.eventKindFilter,
        autoFollow: s.autoFollow,
        eventsFollow: s.eventsFollow,
      }),
    },
  ),
);
