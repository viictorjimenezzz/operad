import { EmptyState } from "@/components/ui/empty-state";
import { JsonView } from "@/components/ui/json-view";
import { Envelope, type EventEnvelope } from "@/lib/types";
import { useMemo } from "react";
import { z } from "zod";

const EventArray = z.array(Envelope);

function findLast<T>(arr: T[], predicate: (item: T) => boolean): T | undefined {
  for (let i = arr.length - 1; i >= 0; i--) {
    const item = arr[i];
    if (item !== undefined && predicate(item)) return item;
  }
  return undefined;
}

export function IODetail({ data }: { data: unknown }) {
  const parsed = EventArray.safeParse(data);
  const events: EventEnvelope[] = useMemo(
    () =>
      parsed.success
        ? (parsed.data.filter(
            (e) => e.type === "agent_event" && (e.kind === "start" || e.kind === "end"),
          ) as EventEnvelope[])
        : [],
    [parsed],
  );

  const lastInput = findLast(events, (e) => e.type === "agent_event" && e.input != null);
  const lastOutput = findLast(events, (e) => e.type === "agent_event" && e.output != null);

  if (!lastInput && !lastOutput) {
    return <EmptyState title="no I/O yet" />;
  }

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      <div className="flex flex-col gap-1">
        <span className="text-[0.68rem] uppercase tracking-[0.08em] text-muted">last input</span>
        {lastInput ? (
          <>
            <span className="font-mono text-[11px] text-muted-2">
              {lastInput.type === "agent_event" ? lastInput.agent_path : ""}
            </span>
            <JsonView value={lastInput.type === "agent_event" ? lastInput.input : null} />
          </>
        ) : (
          <span className="text-xs text-muted">—</span>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-[0.68rem] uppercase tracking-[0.08em] text-muted">last output</span>
        {lastOutput ? (
          <>
            <span className="font-mono text-[11px] text-muted-2">
              {lastOutput.type === "agent_event" ? lastOutput.agent_path : ""}
            </span>
            <JsonView value={lastOutput.type === "agent_event" ? lastOutput.output : null} />
          </>
        ) : (
          <span className="text-xs text-muted">—</span>
        )}
      </div>
    </div>
  );
}
