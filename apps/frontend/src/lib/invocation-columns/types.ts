import type { RunFieldValue, RunRow, RunTableColumn } from "@/components/ui/run-table";
import type { RunSummary } from "@/lib/types";

export type InvocationChild = Omit<RunSummary, "metrics"> & {
  metrics?: Record<string, unknown> | undefined;
  metadata?: Record<string, unknown> | undefined;
  algorithm_metadata?: Record<string, unknown> | undefined;
  parent_run_metadata?: Record<string, unknown> | undefined;
  langfuse_url?: string | null | undefined;
};

export interface AlgorithmColumns {
  algorithmClass: string;
  columns: RunTableColumn[];
  rowMapper: (
    child: InvocationChild,
    parent: RunSummary | null,
    index: number,
    previous: InvocationChild | null,
  ) => RunRow;
  defaultGroupBy?: string;
}

export function baseRow(child: InvocationChild): Omit<RunRow, "fields"> {
  return {
    id: child.run_id,
    identity: child.hash_content ?? child.root_agent_path ?? child.run_id,
    state: child.state,
    startedAt: child.started_at ?? null,
    endedAt: child.last_event_at ?? null,
    durationMs: child.duration_ms ?? null,
  };
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

export function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

export function booleanValue(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

export function metadataValue(child: InvocationChild, key: string): unknown {
  const sources = [child.metadata, child.algorithm_metadata, child.parent_run_metadata];
  for (const source of sources) {
    const record = asRecord(source);
    if (!record) continue;
    if (key in record) return record[key];
  }
  return undefined;
}

export function metadataNumber(child: InvocationChild, ...keys: string[]): number | null {
  for (const key of keys) {
    const value = numberValue(metadataValue(child, key));
    if (value != null) return value;
  }
  return null;
}

export function metadataString(child: InvocationChild, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = stringValue(metadataValue(child, key));
    if (value != null) return value;
  }
  return null;
}

export function metadataBoolean(child: InvocationChild, ...keys: string[]): boolean | null {
  for (const key of keys) {
    const value = booleanValue(metadataValue(child, key));
    if (value != null) return value;
  }
  return null;
}

export function metricNumber(child: InvocationChild, ...keys: string[]): number | null {
  const metrics = asRecord(child.metrics);
  if (!metrics) return null;
  for (const key of keys) {
    const value = numberValue(metrics[key]);
    if (value != null) return value;
  }
  return null;
}

export function diffField(value: string, previous?: string): Extract<RunFieldValue, { kind: "diff" }> {
  return previous === undefined ? { kind: "diff", value } : { kind: "diff", value, previous };
}

export function langfuseField(child: InvocationChild): RunFieldValue {
  return child.langfuse_url
    ? { kind: "link", label: "open", to: child.langfuse_url }
    : { kind: "text", value: "—" };
}
