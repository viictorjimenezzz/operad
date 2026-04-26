import type { StreamStatus } from "@/components/runtime/sse-dispatcher";
import { create } from "zustand";

interface StreamState {
  status: StreamStatus;
  lastReconnectAt: number | null;
  setStatus: (status: StreamStatus) => void;
}

export const useStreamStore = create<StreamState>((set) => ({
  status: "idle",
  lastReconnectAt: null,
  setStatus: (status) =>
    set((prev) => ({
      status,
      lastReconnectAt: status === "reconnecting" ? Date.now() : prev.lastReconnectAt,
    })),
}));
