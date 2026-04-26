import { autoMerge } from "@/lib/data-source";
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
 * Backfill model: TanStack Query fetches the JSON snapshot immediately
 * on mount (staleTime 30s). SSE deltas are merged into the same cache
 * entry via queryClient.setQueryData so there is one source of truth.
 * On SSE reconnect the query is invalidated to re-backfill any gap.
 *
 * Layout JSON shape lives in src/lib/layout-schema.ts; UITree shape
 * is from @json-render/core.
 */
import type { UITree } from "@json-render/core";
import { JSONUIProvider, Renderer } from "@json-render/react";
import { useQueryClient, useQueries } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { z } from "zod";

interface DashboardRendererProps {
  layout: LayoutSpec;
  context: Record<string, string>;
}

const passThrough = z.unknown();

export function DashboardRenderer({ layout, context }: DashboardRendererProps) {
  const entries = useMemo(() => Object.entries(layout.dataSources), [layout]);
  const queryClient = useQueryClient();

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

  useEffect(() => {
    const dispatchers: SSEDispatcher[] = [];
    for (const [name, src] of entries) {
      if (!src.stream) continue;
      const streamUrl = resolvePath(src.stream, context);
      const endpointUrl = resolvePath(src.endpoint, context);
      const queryKey = src.queryKey ?? (["layout", name, endpointUrl] as readonly unknown[]);

      const d = new SSEDispatcher({
        url: streamUrl,
        schema: passThrough,
        onMessage: (delta) => {
          queryClient.setQueryData(queryKey, (current: unknown) => autoMerge(current, delta));
        },
        onStatus: (status) => {
          // Re-backfill the JSON snapshot when the SSE connection is lost so
          // we don't miss events that arrived during the disconnect window.
          if (status === "reconnecting") {
            queryClient.invalidateQueries({ queryKey: queryKey as unknown[] });
          }
        },
      });
      d.open();
      dispatchers.push(d);
    }
    return () => {
      for (const d of dispatchers) d.close();
    };
  }, [entries, context, queryClient]);

  const runId = context.runId ?? "";
  const runEvents = useEventBufferStore((s) => s.eventsByRun.get(runId) ?? EMPTY_EVENTS);

  const queryDatas = queries.map((q) => q.data);

  const tree: UITree = useMemo(() => {
    const queryData: Record<string, unknown> = {};
    entries.forEach(([name], i) => {
      queryData[name] = queryDatas[i];
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
  }, [entries, layout, runEvents, context, queryDatas]);

  return (
    <JSONUIProvider registry={registry}>
      <Renderer tree={tree} registry={registry} />
    </JSONUIProvider>
  );
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
      const targetKey =
        k === "source" ? "data" : k.startsWith("source") ? `data${k.slice("source".length)}` : k;
      out[targetKey] = resolved;
    } else {
      out[k] = v;
    }
  }
  return out;
}
