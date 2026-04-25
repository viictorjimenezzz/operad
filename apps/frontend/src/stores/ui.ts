import { create } from "zustand";
import { persist } from "zustand/middleware";

export type EventKindFilter = "all" | "agent" | "algo" | "error";

interface UIState {
  currentTab: string;
  eventKindFilter: EventKindFilter;
  eventSearch: string;
  autoFollow: boolean;
  eventsFollow: boolean;
  setCurrentTab: (tab: string) => void;
  setEventKindFilter: (f: EventKindFilter) => void;
  setEventSearch: (s: string) => void;
  setAutoFollow: (v: boolean) => void;
  setEventsFollow: (v: boolean) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      currentTab: "overview",
      eventKindFilter: "all",
      eventSearch: "",
      autoFollow: true,
      eventsFollow: true,
      setCurrentTab: (tab) => set({ currentTab: tab }),
      setEventKindFilter: (f) => set({ eventKindFilter: f }),
      setEventSearch: (s) => set({ eventSearch: s }),
      setAutoFollow: (v) => set({ autoFollow: v }),
      setEventsFollow: (v) => set({ eventsFollow: v }),
    }),
    {
      name: "operad.ui",
      partialize: (s) => ({
        eventKindFilter: s.eventKindFilter,
        autoFollow: s.autoFollow,
        eventsFollow: s.eventsFollow,
      }),
    },
  ),
);
