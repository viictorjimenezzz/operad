import {
  EventRow,
  eventPath,
  eventPayload,
  eventSeverityBucket,
  eventSummary,
  spanIdFromMetadata,
} from "@/components/agent-view/page-shell/event-row";
import { Button, EmptyState, JsonView, MarkdownView } from "@/components/ui";
import { useManifest, useRunEvents, useRunSummary } from "@/hooks/use-runs";
import { useUrlState } from "@/hooks/use-url-state";
import { langfuseUrlFor } from "@/lib/langfuse";
import type { Envelope, EventEnvelope } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useEventBufferStore } from "@/stores";
import * as Popover from "@radix-ui/react-popover";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Check, ExternalLink } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";

interface EventsTabProps {
  runId: string;
  defaultKindFilter?: string[];
  defaultPathFilter?: string;
}

type EventTypeFilter = "both" | "agent_event" | "algo_event";
type SeverityFilter = "any" | "low" | "medium" | "high";

const ROW_HEIGHT = 32;
const EVENT_LIMIT = 500;
const EMPTY_EVENTS: EventEnvelope[] = [];

export function EventsTab({ runId, defaultKindFilter, defaultPathFilter }: EventsTabProps) {
  const events = useRunEvents(runId, EVENT_LIMIT);
  const summary = useRunSummary(runId);
  const manifest = useManifest();
  const liveEvents = useEventBufferStore((s) => s.eventsByRun.get(runId) ?? EMPTY_EVENTS);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);
  const followTouchedRef = useRef(false);
  const pinnedToBottomRef = useRef(true);
  const lastCountRef = useRef(0);

  const [kindParam, setKindParam] = useUrlState("kind");
  const [pathParam, setPathParam] = useUrlState("path");
  const [severityParam, setSeverityParam] = useUrlState("sev");
  const [typeParam, setTypeParam] = useUrlState("type");
  const [eventParam, setEventParam] = useUrlState("event");
  const [search, setSearch] = useState("");
  const [live, setLive] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [detailIndex, setDetailIndex] = useState<number | null>(null);
  const [newEventsWaiting, setNewEventsWaiting] = useState(false);

  useEffect(() => {
    if (followTouchedRef.current) return;
    setLive(summary.data?.state === "running");
  }, [summary.data?.state]);

  const snapshotEvents = useMemo(
    () => onlyEventEnvelopes(events.data?.events ?? []),
    [events.data?.events],
  );
  const allEvents = useMemo(
    () => mergeEvents(live ? snapshotEvents.concat(liveEvents) : snapshotEvents),
    [live, liveEvents, snapshotEvents],
  );
  const kindOptions = useMemo(
    () => uniqueSorted(allEvents.map((event) => event.kind)),
    [allEvents],
  );
  const pathOptions = useMemo(() => uniqueSorted(allEvents.map(eventPath)), [allEvents]);
  const defaultKinds = useMemo(
    () => resolveDefaultKinds(defaultKindFilter, allEvents, kindOptions),
    [defaultKindFilter, allEvents, kindOptions],
  );
  const selectedKinds = useMemo(
    () => parseKindFilter(kindParam, defaultKinds, kindOptions),
    [kindParam, defaultKinds, kindOptions],
  );
  const selectedPath = pathParam === "any" ? null : (pathParam ?? defaultPathFilter ?? null);
  const selectedSeverity = parseSeverityFilter(severityParam);
  const selectedType = parseTypeFilter(typeParam);
  const hasSeverityEvents = useMemo(
    () => allEvents.some((event) => event.kind === "gradient_applied"),
    [allEvents],
  );

  const filtered = useMemo(
    () =>
      allEvents.filter((event) =>
        matchesFilters(event, {
          selectedKinds,
          selectedPath,
          selectedSeverity: hasSeverityEvents ? selectedSeverity : "any",
          selectedType,
          search,
        }),
      ),
    [
      allEvents,
      selectedKinds,
      selectedPath,
      selectedSeverity,
      selectedType,
      search,
      hasSeverityEvents,
    ],
  );

  const rowVirtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => viewportRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 12,
  });
  const virtualItems = rowVirtualizer.getVirtualItems();
  const rowsToRender =
    virtualItems.length > 0
      ? virtualItems
      : filtered.map((_, index) => ({
          index,
          key: index,
          size: ROW_HEIGHT,
          start: index * ROW_HEIGHT,
        }));

  useEffect(() => {
    const next = parseEventIndex(eventParam, filtered.length);
    if (next === null) return;
    setActiveIndex(next);
    setDetailIndex(next);
    rowVirtualizer.scrollToIndex(next, { align: "auto" });
  }, [eventParam, filtered.length, rowVirtualizer]);

  useEffect(() => {
    if (filtered.length === 0) {
      setActiveIndex(0);
      setDetailIndex(null);
      return;
    }
    setActiveIndex((current) => clamp(current, 0, filtered.length - 1));
    setDetailIndex((current) => (current === null ? null : clamp(current, 0, filtered.length - 1)));
  }, [filtered.length]);

  useEffect(() => {
    if (filtered.length <= lastCountRef.current) {
      lastCountRef.current = filtered.length;
      return;
    }
    lastCountRef.current = filtered.length;
    if (!live) return;
    if (pinnedToBottomRef.current) {
      rowVirtualizer.scrollToIndex(filtered.length - 1, { align: "end" });
      setNewEventsWaiting(false);
    } else {
      setNewEventsWaiting(true);
    }
  }, [filtered.length, live, rowVirtualizer]);

  const selectEvent = (index: number) => {
    setActiveIndex(index);
    setDetailIndex(index);
    setEventParam(String(index));
  };

  const closeDetail = () => {
    setDetailIndex(null);
    setEventParam(null);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (isInteractive(event.target)) {
      if (event.key !== "/") return;
      event.preventDefault();
      searchRef.current?.focus();
      return;
    }
    if (event.key === "/") {
      event.preventDefault();
      searchRef.current?.focus();
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      closeDetail();
      return;
    }
    if (filtered.length === 0) return;
    if (event.key === "j" || event.key === "ArrowDown") {
      event.preventDefault();
      const next = clamp(activeIndex + 1, 0, filtered.length - 1);
      setActiveIndex(next);
      rowVirtualizer.scrollToIndex(next, { align: "auto" });
      return;
    }
    if (event.key === "k" || event.key === "ArrowUp") {
      event.preventDefault();
      const next = clamp(activeIndex - 1, 0, filtered.length - 1);
      setActiveIndex(next);
      rowVirtualizer.scrollToIndex(next, { align: "auto" });
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      selectEvent(activeIndex);
    }
  };

  const onViewportScroll = () => {
    const el = viewportRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    pinnedToBottomRef.current = distanceFromBottom < 36;
    if (pinnedToBottomRef.current) setNewEventsWaiting(false);
  };

  if (events.isLoading && snapshotEvents.length === 0) {
    return <div className="p-4 text-xs text-muted">loading events...</div>;
  }
  if (events.error && snapshotEvents.length === 0) {
    return (
      <EmptyState
        title="events unavailable"
        description="the dashboard could not load this run's event timeline"
      />
    );
  }

  const selected = detailIndex !== null ? (filtered[detailIndex] ?? null) : null;
  const langfuseUrl = manifest.data?.langfuseUrl ?? null;

  return (
    <div
      role="application"
      // biome-ignore lint/a11y/noNoninteractiveTabindex: the timeline container owns j/k, arrow, enter, escape, and slash keyboard navigation.
      tabIndex={0}
      aria-label="events timeline"
      onKeyDown={onKeyDown}
      className="flex h-full min-h-0 flex-col overflow-hidden p-4 outline-none focus-visible:ring-2 focus-visible:ring-[--color-accent-dim]"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2 border-b border-border pb-3">
        <div className="relative min-w-52 flex-1">
          <input
            ref={searchRef}
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search..."
            className="h-8 w-full rounded border border-border bg-bg-2 px-2 text-[12px] text-text placeholder:text-muted-2 focus:border-border-strong focus:outline-none"
          />
        </div>
        <KindFilter
          kinds={kindOptions}
          selected={selectedKinds}
          defaultKinds={defaultKinds}
          onChange={(next) =>
            setKindParam(next === null || next.length === 0 ? "any" : next.join(","))
          }
        />
        <select
          aria-label="Path filter"
          value={selectedPath ?? "any"}
          onChange={(event) =>
            setPathParam(event.target.value === "any" ? "any" : event.target.value)
          }
          className="h-8 rounded border border-border bg-bg-2 px-2 text-[12px] text-text"
        >
          <option value="any">Path: any</option>
          {pathOptions.map((path) => (
            <option key={path} value={path}>
              {path}
            </option>
          ))}
        </select>
        {hasSeverityEvents ? (
          <select
            aria-label="Severity filter"
            value={selectedSeverity}
            onChange={(event) => setSeverityParam(event.target.value)}
            className="h-8 rounded border border-border bg-bg-2 px-2 text-[12px] text-text"
          >
            <option value="any">Severity: any</option>
            <option value="low">Severity: low</option>
            <option value="medium">Severity: medium</option>
            <option value="high">Severity: high</option>
          </select>
        ) : null}
        <select
          aria-label="Type filter"
          value={selectedType}
          onChange={(event) => setTypeParam(event.target.value)}
          className="h-8 rounded border border-border bg-bg-2 px-2 text-[12px] text-text"
        >
          <option value="both">Show: both</option>
          <option value="agent_event">Show: agent_event</option>
          <option value="algo_event">Show: algo_event</option>
        </select>
        <label className="inline-flex h-8 items-center gap-2 rounded border border-border bg-bg-2 px-2 text-[12px] text-muted">
          <input
            type="checkbox"
            checked={live}
            onChange={(event) => {
              followTouchedRef.current = true;
              setLive(event.target.checked);
            }}
          />
          Live
        </label>
      </div>

      {allEvents.length === 0 ? (
        <EmptyState
          title="no events recorded yet"
          description="this run has not emitted agent or algorithm events yet"
        />
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(320px,0.42fr)]">
          <div className="relative min-h-0 overflow-hidden rounded-md border border-border bg-bg-1">
            <div
              ref={viewportRef}
              onScroll={onViewportScroll}
              className="h-full overflow-auto"
              aria-label="event rows"
            >
              <div
                className="relative w-full"
                style={{ height: `${rowVirtualizer.getTotalSize()}px` }}
              >
                {rowsToRender.map((virtualRow) => {
                  const event = filtered[virtualRow.index];
                  if (!event) return null;
                  return (
                    <EventRow
                      key={eventKey(event, virtualRow.index)}
                      event={event}
                      index={virtualRow.index}
                      active={activeIndex === virtualRow.index}
                      selected={detailIndex === virtualRow.index}
                      onSelect={selectEvent}
                      style={{
                        height: `${virtualRow.size}px`,
                        transform: `translateY(${virtualRow.start}px)`,
                      }}
                    />
                  );
                })}
              </div>
            </div>
            {newEventsWaiting ? (
              <Button
                size="sm"
                variant="primary"
                onClick={() => {
                  rowVirtualizer.scrollToIndex(filtered.length - 1, { align: "end" });
                  pinnedToBottomRef.current = true;
                  setNewEventsWaiting(false);
                }}
                className="absolute bottom-3 left-1/2 -translate-x-1/2"
              >
                new events down
              </Button>
            ) : null}
          </div>
          <EventDetail event={selected} langfuseUrl={langfuseUrl} onClose={closeDetail} />
        </div>
      )}
    </div>
  );
}

function KindFilter({
  kinds,
  selected,
  defaultKinds,
  onChange,
}: {
  kinds: string[];
  selected: string[];
  defaultKinds: string[];
  onChange: (next: string[] | null) => void;
}) {
  const label =
    selected.length === 0
      ? "Kind: any"
      : selected.length === 1
        ? `Kind: ${selected[0]}`
        : `Kind: ${selected.length}`;

  const toggle = (kind: string) => {
    const next = new Set(selected);
    if (next.has(kind)) next.delete(kind);
    else next.add(kind);
    onChange([...next]);
  };

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <Button size="sm" variant="default" className="h-8">
          {label}
        </Button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={6}
          className="z-50 min-w-48 rounded-md border border-border-strong bg-bg-1 p-1 shadow-[var(--shadow-popover)]"
        >
          <button
            type="button"
            onClick={() => onChange(null)}
            className="flex h-7 w-full items-center gap-2 rounded px-2 text-left text-[12px] text-muted transition-colors hover:bg-bg-2 hover:text-text"
          >
            <CheckMark checked={selected.length === 0} />
            <span>any</span>
          </button>
          {defaultKinds.length > 0 ? (
            <button
              type="button"
              onClick={() => onChange(defaultKinds)}
              className="flex h-7 w-full items-center gap-2 rounded px-2 text-left text-[12px] text-muted transition-colors hover:bg-bg-2 hover:text-text"
            >
              <CheckMark checked={sameSet(selected, defaultKinds)} />
              <span>default</span>
            </button>
          ) : null}
          {kinds.map((kind) => (
            <button
              key={kind}
              type="button"
              onClick={() => toggle(kind)}
              className="flex h-7 w-full items-center gap-2 rounded px-2 text-left text-[12px] text-muted transition-colors hover:bg-bg-2 hover:text-text"
            >
              <CheckMark checked={selected.includes(kind)} />
              <span>{kind}</span>
            </button>
          ))}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function CheckMark({ checked }: { checked: boolean }) {
  return (
    <span
      className={cn(
        "flex h-4 w-4 items-center justify-center rounded border border-border",
        checked && "border-accent bg-accent text-bg",
      )}
    >
      {checked ? <Check size={11} /> : null}
    </span>
  );
}

function EventDetail({
  event,
  langfuseUrl,
  onClose,
}: {
  event: EventEnvelope | null;
  langfuseUrl: string | null;
  onClose: () => void;
}) {
  if (!event) {
    return (
      <div className="overflow-auto rounded-md border border-border bg-bg-1">
        <EmptyState title="select an event" description="click a row to inspect its payload" />
      </div>
    );
  }

  const path = eventPath(event);
  const spanId = spanIdFromMetadata(event.metadata);
  const eventHref =
    langfuseUrl && spanId ? langfuseUrlFor(langfuseUrl, event.run_id, spanId) : null;

  return (
    <div className="min-h-0 overflow-auto rounded-md border border-border bg-bg-1 p-3">
      <div className="mb-3 flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-[11px] uppercase tracking-[0.06em] text-muted">{event.type}</div>
          <div className="truncate font-mono text-sm text-text" title={path}>
            {path}
          </div>
          <div className="font-mono text-xs text-muted">{event.kind}</div>
        </div>
        {eventHref ? (
          <a
            href={eventHref}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-7 items-center gap-1 rounded border border-border bg-bg-2 px-2 text-[11px] text-accent transition-colors hover:border-border-strong"
          >
            Open in Langfuse
            <ExternalLink size={12} />
          </a>
        ) : null}
        <Button size="sm" variant="ghost" onClick={onClose}>
          Close
        </Button>
      </div>
      <div className="flex flex-col gap-3 text-xs">
        <Section label="summary">
          <div className="rounded border border-border bg-bg-2 p-2 text-muted">
            {eventSummary(event)}
          </div>
        </Section>
        {event.type === "agent_event" && event.input != null ? (
          <Section label="input">
            <JsonView value={event.input} />
          </Section>
        ) : null}
        {event.type === "agent_event" && event.output != null ? (
          <Section label="output">
            <JsonView value={event.output} />
          </Section>
        ) : null}
        {event.type === "agent_event" && event.error != null ? (
          <Section label="error">
            <JsonView value={event.error} />
          </Section>
        ) : null}
        {event.type === "algo_event" ? <PayloadDetail payload={event.payload} /> : null}
        <Section label="metadata">
          <JsonView value={event.metadata} collapsed />
        </Section>
      </div>
    </div>
  );
}

function PayloadDetail({ payload }: { payload: Record<string, unknown> }) {
  const entries = Object.entries(payload);
  if (entries.length === 0) {
    return (
      <Section label="payload">
        <JsonView value={payload} collapsed />
      </Section>
    );
  }
  return (
    <>
      {entries.map(([key, value]) =>
        typeof value === "string" && isMarkdownKey(key) ? (
          <Section key={key} label={key}>
            <MarkdownView value={value} />
          </Section>
        ) : (
          <Section key={key} label={key}>
            <JsonView value={value} collapsed />
          </Section>
        ),
      )}
    </>
  );
}

function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[0.68rem] uppercase tracking-[0.08em] text-muted">{label}</span>
      {children}
    </div>
  );
}

function onlyEventEnvelopes(events: Envelope[]): EventEnvelope[] {
  return events.filter((event): event is EventEnvelope => isEventEnvelope(event));
}

function isEventEnvelope(event: Envelope): event is EventEnvelope {
  return event.type === "agent_event" || event.type === "algo_event";
}

function mergeEvents(events: EventEnvelope[]): EventEnvelope[] {
  const seen = new Set<string>();
  const merged: EventEnvelope[] = [];
  for (const event of events) {
    const key = eventIdentity(event);
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(event);
  }
  return merged.sort((a, b) => a.started_at - b.started_at);
}

function eventKey(event: EventEnvelope, index: number): string {
  return `${eventIdentity(event)}:${index}`;
}

function eventIdentity(event: EventEnvelope): string {
  return [
    event.run_id,
    event.type,
    event.kind,
    eventPath(event),
    event.started_at,
    event.finished_at ?? "",
  ].join(":");
}

function matchesFilters(
  event: EventEnvelope,
  filters: {
    selectedKinds: string[];
    selectedPath: string | null;
    selectedSeverity: SeverityFilter;
    selectedType: EventTypeFilter;
    search: string;
  },
): boolean {
  if (filters.selectedType !== "both" && event.type !== filters.selectedType) return false;
  if (filters.selectedKinds.length > 0 && !filters.selectedKinds.includes(event.kind)) return false;
  if (filters.selectedPath && eventPath(event) !== filters.selectedPath) return false;
  if (filters.selectedSeverity !== "any") {
    if (eventSeverityBucket(event) !== filters.selectedSeverity) return false;
  }
  if (!filters.search.trim()) return true;
  const needle = filters.search.toLowerCase();
  const haystack = [
    event.type,
    event.kind,
    eventPath(event),
    String(eventSummary(event)),
    JSON.stringify(eventPayload(event)),
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(needle);
}

function resolveDefaultKinds(
  explicit: string[] | undefined,
  events: EventEnvelope[],
  kindOptions: string[],
): string[] {
  const requested = explicit ?? inferDefaultKinds(events);
  if (requested.length === 0) return [];
  const available = requested.filter((kind) => kindOptions.includes(kind));
  return available.length > 0 || events.length === 0 ? available : [];
}

function inferDefaultKinds(events: EventEnvelope[]): string[] {
  const algoPath =
    events.find((event) => event.type === "algo_event")?.algorithm_path.toLowerCase() ?? "";
  if (algoPath.includes("sweep")) return ["cell"];
  if (algoPath.includes("debate")) return ["round"];
  if (algoPath.includes("evo")) return ["generation"];
  if (algoPath.includes("trainer")) return ["batch_end", "gradient_applied", "iteration"];
  if (algoPath.includes("beam")) return ["candidate"];
  if (algoPath.includes("opro")) return ["iteration"];
  if (algoPath.includes("self") || algoPath.includes("srefine")) return ["iteration"];
  if (algoPath.includes("verifier")) return ["iteration"];
  if (algoPath.includes("research")) return ["plan", "iteration"];
  return [];
}

function parseKindFilter(raw: string | null, defaults: string[], kinds: string[]): string[] {
  if (raw === "any") return [];
  if (raw === null || raw === "") return defaults;
  return raw.split(",").filter((kind) => kinds.includes(kind));
}

function parseSeverityFilter(raw: string | null): SeverityFilter {
  return raw === "low" || raw === "medium" || raw === "high" ? raw : "any";
}

function parseTypeFilter(raw: string | null): EventTypeFilter {
  return raw === "agent_event" || raw === "algo_event" ? raw : "both";
}

function parseEventIndex(raw: string | null, length: number): number | null {
  if (raw === null || raw === "") return null;
  const index = Number(raw);
  if (!Number.isInteger(index) || index < 0 || index >= length) return null;
  return index;
}

function uniqueSorted(values: string[]): string[] {
  return [...new Set(values)].sort((a, b) => a.localeCompare(b));
}

function sameSet(left: string[], right: string[]): boolean {
  if (left.length !== right.length) return false;
  const set = new Set(left);
  return right.every((item) => set.has(item));
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function isInteractive(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && Boolean(target.closest("button,a,input,textarea,select"));
}

function isMarkdownKey(key: string): boolean {
  return /text|prompt|proposal|critique|plan|message|content/i.test(key);
}
