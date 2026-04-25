import { type LayoutSpec, resolvePath } from "@/lib/layout-schema";
import { SSEDispatcher } from "@/lib/sse-dispatcher";
import type { EventEnvelope } from "@/lib/types";
import { registry } from "@/registry/registry";
import { resolveSource } from "@/registry/resolve";
import { useEventBufferStore } from "@/stores";
/**
 * The single call site for @json-render. Reads a LayoutSpec, opens
 * one TanStack query per dataSource, optionally subscribes to that
 * data-source's `.sse` stream, resolves every prop's `source:`
 * expression against the running query results, and forwards a
 * fully-typed UITree into <Renderer />.
 *
 * Layout JSON shape lives in src/lib/layout-schema.ts; UITree shape
 * is from @json-render/core.
 */
import type { UITree } from "@json-render/core";
import { Renderer } from "@json-render/react";
import { useQueries } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { z } from "zod";

interface DashboardRendererProps {
  layout: LayoutSpec;
  context: Record<string, string>;
}

const passThrough = z.unknown();

export function DashboardRenderer({ layout, context }: DashboardRendererProps) {
  const entries = useMemo(() => Object.entries(layout.dataSources), [layout]);

  const queries = useQueries({
    queries: entries.map(([name, src]) => {
      const url = resolvePath(src.endpoint, context);
      return {
        queryKey: src.queryKey ?? (["layout", name, url] as readonly unknown[]),
        queryFn: async () => {
          const r = await fetch(url);
          if (!r.ok) throw new Error(`${r.status} ${r.statusText} <- ${url}`);
          return (await r.json()) as unknown;
        },
        staleTime: 30_000,
      };
    }),
  });

  const [streamed, setStreamed] = useState<Record<string, unknown>>({});

  useEffect(() => {
    const dispatchers: SSEDispatcher[] = [];
    for (const [name, src] of entries) {
      if (!src.stream) continue;
      const url = resolvePath(src.stream, context);
      const d = new SSEDispatcher({
        url,
        schema: passThrough,
        onMessage: (snap) => setStreamed((prev) => ({ ...prev, [name]: snap })),
      });
      d.open();
      dispatchers.push(d);
    }
    return () => {
      for (const d of dispatchers) d.close();
    };
  }, [entries, context]);

  const runId = context.runId ?? "";
  const runEvents = useEventBufferStore((s) => s.eventsByRun.get(runId) ?? EMPTY_EVENTS);

  // Snapshot every query's data array so we can pass them as a stable
  // dependency to useMemo (queries[i].data is the underlying primitive
  // we depend on; rolling them up keeps the dep list tidy).
  const queryDatas = queries.map((q) => q.data);

  const tree: UITree = useMemo(() => {
    const queryData: Record<string, unknown> = {};
    entries.forEach(([name], i) => {
      queryData[name] = streamed[name] ?? queryDatas[i];
    });
    const ctx = {
      context,
      queries: queryData,
      runEvents: runEvents as EventEnvelope[],
    };
    const elements: UITree["elements"] = {};
    for (const [id, el] of Object.entries(layout.spec.elements)) {
      const node: UITree["elements"][string] = {
        key: id,
        type: el.type,
        props: resolveProps(el.props ?? {}, ctx),
      };
      if (el.children !== undefined) node.children = el.children;
      elements[id] = node;
    }
    return { root: layout.spec.root, elements };
  }, [entries, layout, runEvents, context, queryDatas, streamed]);

  return <Renderer tree={tree} registry={registry} />;
}

const EMPTY_EVENTS: EventEnvelope[] = [];

function resolveProps(
  props: Record<string, unknown>,
  ctx: {
    context: Record<string, string>;
    queries: Record<string, unknown>;
    runEvents: EventEnvelope[];
  },
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(props)) {
    if (typeof v === "string" && v.startsWith("$")) {
      const resolved = resolveSource(v, ctx);
      // `source` -> `data` so the registry components don't have to know
      // about the layout-language naming convention.
      const targetKey =
        k === "source" ? "data" : k.startsWith("source") ? `data${k.slice("source".length)}` : k;
      out[targetKey] = resolved;
    } else {
      out[k] = v;
    }
  }
  return out;
}
