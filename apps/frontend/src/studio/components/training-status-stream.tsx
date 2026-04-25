import { SSEDispatcher } from "@/lib/sse-dispatcher";
import { Badge } from "@/shared/ui/badge";
import { useEffect, useState } from "react";
import { z } from "zod";

const TrainingEvent = z.object({ kind: z.string() }).passthrough();

interface TrainingStatusStreamProps {
  jobName: string;
}

export function TrainingStatusStream({ jobName }: TrainingStatusStreamProps) {
  const [events, setEvents] = useState<{ kind: string; raw: unknown }[]>([]);
  const [done, setDone] = useState(false);

  useEffect(() => {
    setEvents([]);
    setDone(false);
    const url = `/jobs/${encodeURIComponent(jobName)}/train/stream`;
    const d = new SSEDispatcher<z.infer<typeof TrainingEvent>>({
      url,
      schema: TrainingEvent,
      onMessage: (event) => {
        setEvents((prev) => [...prev, { kind: event.kind, raw: event }]);
        if (event.kind === "finished" || event.kind === "error") {
          setDone(true);
          d.close();
        }
      },
    });
    d.open();
    return () => d.close();
  }, [jobName]);

  return (
    <div className="flex flex-col gap-1 rounded-md border border-border bg-bg-2 p-2 font-mono text-[11px]">
      {events.length === 0 && !done && <span className="text-muted">waiting for events…</span>}
      {events.map((e, i) => (
        <div key={i} className="flex items-center gap-2">
          <Badge
            variant={e.kind === "finished" ? "ended" : e.kind === "error" ? "error" : "default"}
          >
            {e.kind}
          </Badge>
          <code className="truncate text-muted">{JSON.stringify(e.raw).slice(0, 200)}</code>
        </div>
      ))}
      {done && events.find((e) => e.kind === "error") && (
        <span className="mt-1 text-err">training failed — see above</span>
      )}
      {done && !events.find((e) => e.kind === "error") && (
        <span className="mt-1 text-ok">training finished</span>
      )}
    </div>
  );
}
