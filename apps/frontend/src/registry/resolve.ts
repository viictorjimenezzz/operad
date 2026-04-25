/**
 * Resolve a layout `source` expression against the active context.
 *
 * Source grammar (intentionally tiny, no Handlebars / Liquid):
 *   $context.<key>           — values from <DashboardRenderer context>
 *   $queries.<name>[.path]   — TanStack query result by data-source name
 *   $run.events              — current run's event buffer (Zustand)
 *   $run.summary             — alias for $queries.summary if present
 *
 * Returns `undefined` if the path doesn't resolve (callers render an
 * empty/loading state rather than crashing).
 */
import type { EventEnvelope } from "@/lib/types";

export interface ResolveContext {
  context: Record<string, string>;
  queries: Record<string, unknown>;
  runEvents: EventEnvelope[];
}

export function resolveSource(expr: unknown, ctx: ResolveContext): unknown {
  if (typeof expr !== "string") return expr;
  if (!expr.startsWith("$")) return expr;
  const [head, ...rest] = expr.split(".");
  if (head === "$context") {
    return rest[0] !== undefined ? ctx.context[rest[0]] : ctx.context;
  }
  if (head === "$run") {
    if (rest[0] === "events") return ctx.runEvents;
    if (rest[0] === "summary") return ctx.queries.summary;
    return undefined;
  }
  if (head === "$queries") {
    if (rest.length === 0) return ctx.queries;
    const name = rest[0];
    if (name === undefined) return undefined;
    let value: unknown = ctx.queries[name];
    for (const segment of rest.slice(1)) {
      if (value === null || value === undefined) return undefined;
      if (typeof value !== "object") return undefined;
      value = (value as Record<string, unknown>)[segment];
    }
    return value;
  }
  return expr;
}

/**
 * Resolve every value in a props object whose key starts with `source`
 * (e.g. `source`, `dataSource`). Other props pass through unchanged.
 * Layouts annotate which props need resolution by naming them `source*`.
 */
export function resolveProps(
  props: Record<string, unknown> | undefined,
  ctx: ResolveContext,
): Record<string, unknown> {
  if (!props) return {};
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(props)) {
    if (k === "source" || k.startsWith("source")) {
      out[k.replace(/^source/, "data").replace(/^data$/, "data") || "data"] = resolveSource(v, ctx);
    } else if (k === "runId") {
      out.runId = resolveSource(v, ctx);
    } else {
      out[k] = v;
    }
  }
  return out;
}
