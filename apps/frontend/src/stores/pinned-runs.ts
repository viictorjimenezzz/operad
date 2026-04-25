import { create } from "zustand";
import { persist } from "zustand/middleware";

const MAX_PINS = 20;

interface PinnedRunsState {
  pinned: string[];
  pin: (runId: string) => boolean;
  unpin: (runId: string) => void;
  toggle: (runId: string) => void;
  clear: () => void;
  isPinned: (runId: string) => boolean;
}

export const usePinnedRunsStore = create<PinnedRunsState>()(
  persist(
    (set, get) => ({
      pinned: [],
      pin: (runId) => {
        const { pinned } = get();
        if (pinned.includes(runId)) return true;
        if (pinned.length >= MAX_PINS) return false;
        set({ pinned: [...pinned, runId] });
        return true;
      },
      unpin: (runId) =>
        set((s) => ({ pinned: s.pinned.filter((id) => id !== runId) })),
      toggle: (runId) => {
        const { pinned, pin, unpin } = get();
        pinned.includes(runId) ? unpin(runId) : pin(runId);
      },
      clear: () => set({ pinned: [] }),
      isPinned: (runId) => get().pinned.includes(runId),
    }),
    {
      name: "operad:pinned-runs:v1",
      partialize: (s) => ({ pinned: s.pinned }),
    },
  ),
);
