import type { CostTotals, GlobalStats, SlotOccupancyEntry } from "@/lib/types";
import { create } from "zustand";

interface StatsState {
  slotOccupancy: SlotOccupancyEntry[];
  costTotals: Record<string, CostTotals>;
  globalStats: GlobalStats | null;
  setSlots: (s: SlotOccupancyEntry[]) => void;
  setCosts: (t: Record<string, CostTotals>) => void;
  setGlobal: (s: GlobalStats) => void;
}

export const useStatsStore = create<StatsState>((set) => ({
  slotOccupancy: [],
  costTotals: {},
  globalStats: null,
  setSlots: (slotOccupancy) => set({ slotOccupancy }),
  setCosts: (costTotals) => set({ costTotals }),
  setGlobal: (globalStats) => set({ globalStats }),
}));
