/**
 * Resolve a layout `source` expression against the active context.
 *
 * Source grammar (intentionally tiny, no Handlebars / Liquid):
 *   $context.<key>           — values from <DashboardRenderer context>
 *   $queries.<name>[.path]   — TanStack query result by data-source name
 *   $run.events              — current run's event buffer (Zustand)
 *   $run.summary             — alias for $queries.summary if present
 *   $expr:<fn>(<arg>)        — call a whitelisted helper, where <arg> is
 *                              itself a source expression resolved first.
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

type Helper = (arg: unknown, ctx: ResolveContext) => unknown;

function asObject(arg: unknown): Record<string, unknown> | null {
  if (arg && typeof arg === "object" && !Array.isArray(arg)) {
    return arg as Record<string, unknown>;
  }
  return null;
}

const HELPERS: Record<string, Helper> = {
  latest: (arg) => {
    if (Array.isArray(arg)) return arg[arg.length - 1] ?? null;
    const obj = asObject(arg);
    if (obj && Array.isArray(obj.invocations)) {
      const arr = obj.invocations as unknown[];
      return arr[arr.length - 1] ?? null;
    }
    return null;
  },
  count: (arg) => {
    if (Array.isArray(arg)) return arg.length;
    const obj = asObject(arg);
    if (obj && Array.isArray(obj.invocations)) return (obj.invocations as unknown[]).length;
    if (obj && Array.isArray(obj.children)) return (obj.children as unknown[]).length;
    if (obj && Array.isArray(obj.agents)) return (obj.agents as unknown[]).length;
    return 0;
  },
  length: (arg) => {
    if (Array.isArray(arg)) return arg.length;
    const obj = asObject(arg);
    return obj ? Object.keys(obj).length : 0;
  },
  hashes: (arg) => {
    const rows = Array.isArray(arg) ? arg : (asObject(arg)?.invocations ?? []);
    const last = (rows as Array<Record<string, unknown>>).at(-1) ?? null;
    if (!last) return {};
    return {
      hash_model: last.hash_model ?? null,
      hash_prompt: last.hash_prompt ?? null,
      hash_graph: last.hash_graph ?? null,
      hash_input: last.hash_input ?? null,
      hash_output_schema: last.hash_output_schema ?? null,
      hash_config: last.hash_config ?? null,
      hash_content: last.hash_content ?? null,
    };
  },
  pluck: (arg) => {
    if (typeof arg !== "string") return undefined;
    return arg;
  },
};

export function resolveSource(expr: unknown, ctx: ResolveContext): unknown {
  if (typeof expr !== "string") return expr;
  if (!expr.startsWith("$")) return expr;

  // $expr:<fn>(<inner>) — call a whitelisted helper.
  if (expr.startsWith("$expr:")) {
    const match = expr.match(/^\$expr:([a-zA-Z][a-zA-Z0-9_]*)\((.*)\)$/);
    if (!match) return undefined;
    const fn = match[1];
    const innerExpr = match[2] ?? "";
    if (!fn) return undefined;
    const helper = HELPERS[fn];
    if (!helper) return undefined;
    const innerValue = resolveSource(innerExpr, ctx);
    return helper(innerValue, ctx);
  }

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
