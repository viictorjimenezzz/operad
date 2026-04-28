import { EventRow } from "@/components/agent-view/page-shell/event-row";
import { useAgentEvents } from "@/hooks/use-runs";
import type { AgentEventEnvelope, EventEnvelope } from "@/lib/types";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef, useState } from "react";

const ROW_HEIGHT = 32;
const TAIL_SIZE = 200;

export function TabAgentEvents({ runId, agentPath }: { runId: string; agentPath: string }) {
  const query = useAgentEvents(runId, agentPath);
  const [showAll, setShowAll] = useState(false);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  if (query.isLoading) {
    return <div className="p-5 text-[12px] text-muted-2">loading events…</div>;
  }

  const allEvents = (query.data?.events ?? []).filter(
    (e): e is AgentEventEnvelope => e.type === "agent_event",
  ) as EventEnvelope[];

  if (allEvents.length === 0) {
    return (
      <div className="p-5 text-[12px] text-muted-2">
        no agent events recorded for this path yet
      </div>
    );
  }

  const truncated = !showAll && allEvents.length > TAIL_SIZE;
  const events = truncated ? allEvents.slice(-TAIL_SIZE) : allEvents;

  return (
    <div className="flex h-full flex-col">
      {truncated ? (
        <div className="flex items-center gap-2 border-b border-border px-3 py-2">
          <span className="text-[11px] text-muted-2">
            showing last {TAIL_SIZE} of {allEvents.length} events
          </span>
          <button
            type="button"
            onClick={() => setShowAll(true)}
            className="rounded border border-border bg-bg-2 px-2 py-0.5 text-[11px] text-muted transition-colors hover:border-border-strong hover:text-text"
          >
            show all
          </button>
        </div>
      ) : null}
      <VirtualEventList
        events={events}
        viewportRef={viewportRef}
        selectedIndex={selectedIndex}
        onSelect={setSelectedIndex}
      />
    </div>
  );
}

function VirtualEventList({
  events,
  viewportRef,
  selectedIndex,
  onSelect,
}: {
  events: EventEnvelope[];
  viewportRef: React.RefObject<HTMLDivElement | null>;
  selectedIndex: number | null;
  onSelect: (index: number) => void;
}) {
  const rowVirtualizer = useVirtualizer({
    count: events.length,
    getScrollElement: () => viewportRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });

  return (
    <div ref={viewportRef} className="min-h-0 flex-1 overflow-auto" aria-label="agent event rows">
      <div
        className="relative w-full"
        style={{ height: `${rowVirtualizer.getTotalSize()}px` }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const event = events[virtualRow.index];
          if (!event) return null;
          return (
            <EventRow
              key={virtualRow.index}
              event={event}
              index={virtualRow.index}
              active={false}
              selected={selectedIndex === virtualRow.index}
              onSelect={onSelect}
              style={{
                height: `${virtualRow.size}px`,
                transform: `translateY(${virtualRow.start}px)`,
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
