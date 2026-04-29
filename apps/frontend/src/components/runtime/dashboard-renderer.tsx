import { ParametersTab } from "@/components/agent-view/parameter-evolution/parameters-tab";
import { TrainerTapeView } from "@/components/algorithms/trainer/tape-view";
import { registry as baseRegistry } from "@/components/registry";
import { InvocationsTab } from "@/components/runtime/invocations-tab";
import {
  type ResolveContext,
  resolveProps,
  resolveSource,
} from "@/components/runtime/source-resolver";
import { SSEDispatcher } from "@/components/runtime/sse-dispatcher";
import { type HashKey, HashRow } from "@/components/ui/hash-row";
import { autoMerge } from "@/lib/data-source";
import {
  type ElementSpec,
  type LayoutSpec,
  type TabsElementSpec,
  resolvePath,
} from "@/lib/layout-schema";
import type { EventEnvelope } from "@/lib/types";
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
import type { ComponentRegistry } from "@json-render/react";
import { useQueries, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback, useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

interface DashboardRendererProps {
  layout: LayoutSpec;
  context: Record<string, string>;
  tabsTrailing?: ReactNode;
}

const passThrough = z.unknown();
const registry: ComponentRegistry = {
  ...baseRegistry,
  HashRow: ({ element }) => {
    const props = element.props as {
      current?: Partial<Record<HashKey, string | null>>;
      dataCurrent?: Partial<Record<HashKey, string | null>>;
      previous?: Partial<Record<HashKey, string | null>>;
      dataPrevious?: Partial<Record<HashKey, string | null>>;
      size?: "sm" | "md";
    };
    const previous = props.previous ?? props.dataPrevious;
    return (
      <HashRow
        current={props.current ?? props.dataCurrent ?? {}}
        {...(previous ? { previous } : {})}
        size={props.size ?? "sm"}
      />
    );
  },
  ParametersTab: ({ element }) => {
    const props = element.props as {
      runId?: string;
      hashContent?: string;
      scope?: "run" | "group";
    };
    return (
      <div className="h-full overflow-auto p-4">
        <ParametersTab
          {...(props.runId ? { runId: props.runId } : {})}
          {...(props.hashContent ? { hashContent: props.hashContent } : {})}
          scope={props.scope ?? "run"}
        />
      </div>
    );
  },
  InvocationsTab: ({ element }) => {
    const props = element.props as {
      runId?: string;
      algorithmClass?: string | null;
      defaultGroupBy?: string;
    };
    return (
      <InvocationsTab
        runId={props.runId ?? ""}
        algorithmClass={props.algorithmClass ?? null}
        {...(props.defaultGroupBy ? { defaultGroupBy: props.defaultGroupBy } : {})}
      />
    );
  },
  TrainerTapeView: ({ element }) => {
    const props = element.props as {
      runId?: string;
      dataTape?: unknown;
    };
    return (
      <TrainerTapeView {...(props.runId ? { runId: props.runId } : {})} dataTape={props.dataTape} />
    );
  },
};

export function DashboardRenderer({ layout, context, tabsTrailing }: DashboardRendererProps) {
  const entries = useMemo(() => Object.entries(layout.dataSources), [layout]);
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  // Tab id -> layout element id. When the URL carries a tab id that
  // doesn't exist in the current layout (e.g. user navigated from
  // EvoGradient ?tab=lineage to OPRO whose tabs are different), we
  // ignore it instead of leaving the page in an unrenderable state.
  const knownTabIds = useMemo(() => {
    const ids = new Set<string>();
    for (const el of Object.values(layout.spec.elements)) {
      if (isTabsElement(el)) {
        for (const tab of el.props.tabs) ids.add(tab.id);
      }
    }
    return ids;
  }, [layout]);
  const setActiveTab = useCallback(
    (tabId: string) => {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);
          next.set("tab", tabId);
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const queries = useQueries({
    queries: entries.map(([name, src]) => {
      const url = resolvePath(src.endpoint, context);
      const queryKey = dataSourceQueryKey(name, url, src.queryKey);
      return {
        queryKey,
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
      const queryKey = dataSourceQueryKey(name, endpointUrl, src.queryKey);

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
    const safeTabParam = tabParam && knownTabIds.has(tabParam) ? tabParam : null;
    for (const [id, el] of Object.entries(layout.spec.elements)) {
      if (isTabsElement(el)) {
        const tabs = resolveTabs(el.props.tabs, el.children, ctx);
        const activeTab = tabs.find((tab) => tab.id === safeTabParam)?.id ?? tabs[0]?.id ?? "";
        const activeChildId = tabs.find((tab) => tab.id === activeTab)?.childId;
        elements[id] = {
          key: id,
          type: el.type,
          props: {
            tabs: tabs.map(({ childId: _childId, ...tab }) => tab),
            activeTab,
            onTabChange: setActiveTab,
            ...(id === layout.spec.root && tabsTrailing ? { trailing: tabsTrailing } : {}),
          },
          children: activeChildId ? [activeChildId] : [],
        };
        continue;
      }
      const node: UITree["elements"][string] = {
        key: id,
        type: el.type,
        props: resolveProps(el.props ?? {}, ctx),
      };
      if (el.children !== undefined) node.children = el.children;
      elements[id] = node;
    }
    return { root: layout.spec.root, elements };
  }, [
    entries,
    layout,
    runEvents,
    context,
    queryDatas,
    tabParam,
    knownTabIds,
    setActiveTab,
    tabsTrailing,
  ]);

  return (
    <JSONUIProvider registry={registry}>
      <Renderer tree={tree} registry={registry} />
    </JSONUIProvider>
  );
}

const EMPTY_EVENTS: EventEnvelope[] = [];

type LayoutTab = {
  id: string;
  label: string;
  badge?: string | number | undefined;
  condition?: string | undefined;
};

type ResolvedTab = {
  id: string;
  label: string;
  badge?: string | number;
  childId: string | undefined;
};

function isTabsElement(element: ElementSpec): element is TabsElementSpec {
  const props = (element as Partial<TabsElementSpec>).props;
  return element.type === "Tabs" && Array.isArray(props?.tabs);
}

function resolveTabs(tabs: LayoutTab[], children: string[], ctx: ResolveContext): ResolvedTab[] {
  return tabs
    .map((tab, index) => {
      const conditionValue =
        tab.condition === undefined ? true : Boolean(resolveSource(tab.condition, ctx));
      if (!conditionValue) return null;
      const childId = children.includes(tab.id) ? tab.id : children[index];
      const badge =
        typeof tab.badge === "string" && tab.badge.startsWith("$")
          ? resolveSource(tab.badge, ctx)
          : tab.badge;
      return {
        id: tab.id,
        label: tab.label,
        ...(typeof badge === "string" || typeof badge === "number" ? { badge } : {}),
        childId,
      };
    })
    .filter((tab): tab is ResolvedTab => tab !== null);
}

function dataSourceQueryKey(
  name: string,
  url: string,
  explicit: readonly unknown[] | undefined,
): readonly unknown[] {
  if (explicit) return explicit;
  const summary = url.match(/^\/runs\/([^/]+)\/summary$/);
  if (summary?.[1]) return ["run", "summary", summary[1]] as const;
  const invocations = url.match(/^\/runs\/([^/]+)\/invocations$/);
  if (invocations?.[1]) return ["run", "invocations", invocations[1]] as const;
  const events = url.match(/^\/runs\/([^/]+)\/events(?:\?limit=(\d+))?$/);
  if (events?.[1]) return ["run", "events", events[1], Number(events[2] ?? 500)] as const;
  return ["layout", name, url] as const;
}
