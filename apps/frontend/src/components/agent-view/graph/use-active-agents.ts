import { useEventBufferStore } from "@/stores";
import { useMemo } from "react";

/**
 * Returns the set of agent_paths currently between an `agent_start`
 * envelope and the matching `agent_end` (or `agent_error`). Used to
 * pulse edges live during a run.
 */
export function useActiveAgents(runId: string): Set<string> {
  const events = useEventBufferStore((s) => s.eventsByRun.get(runId) ?? []);
  return useMemo(() => {
    const active = new Set<string>();
    for (const env of events) {
      if (env.type !== "agent_event") continue;
      if (env.kind === "start") active.add(env.agent_path);
      else if (env.kind === "end" || env.kind === "error") active.delete(env.agent_path);
    }
    return active;
  }, [events]);
}
