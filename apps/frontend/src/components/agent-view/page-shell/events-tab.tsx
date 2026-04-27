import { EventTimeline } from "@/components/panels/event-timeline";
import { EmptyState } from "@/components/ui";
import { useRunEvents } from "@/hooks/use-runs";
import { useMemo } from "react";

interface EventsTabProps {
  runId: string;
  defaultKindFilter?: string[];
}

export function EventsTab({ runId, defaultKindFilter }: EventsTabProps) {
  const events = useRunEvents(runId);
  const filtered = useMemo(() => {
    const rows = events.data?.events ?? [];
    if (!defaultKindFilter || defaultKindFilter.length === 0) return rows;
    const allowed = new Set(defaultKindFilter);
    return rows.filter((event) => "kind" in event && allowed.has(event.kind));
  }, [events.data, defaultKindFilter]);

  if (events.isLoading) {
    return <div className="p-4 text-xs text-muted">loading events...</div>;
  }
  if (events.error) {
    return (
      <EmptyState
        title="events unavailable"
        description="the dashboard could not load this run's event timeline"
      />
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <EventTimeline data={filtered} />
    </div>
  );
}
