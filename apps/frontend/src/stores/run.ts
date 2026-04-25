import { create } from "zustand";

interface RunState {
  currentRunId: string | null;
  selectedEventIdx: number;
  setCurrentRun: (runId: string | null) => void;
  setSelectedEventIdx: (idx: number) => void;
}

export const useRunStore = create<RunState>((set) => ({
  currentRunId: null,
  selectedEventIdx: -1,
  setCurrentRun: (runId) => set({ currentRunId: runId, selectedEventIdx: -1 }),
  setSelectedEventIdx: (idx) => set({ selectedEventIdx: idx }),
}));
