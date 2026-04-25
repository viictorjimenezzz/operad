/**
 * Merge semantics for data sources that combine a JSON snapshot with
 * live SSE deltas. Used by DashboardRenderer to keep one source of truth
 * (the TanStack Query cache) instead of a parallel streamed-state map.
 *
 * autoMerge heuristic:
 *   - current is an array AND delta is a non-array object → append-dedupe
 *   - delta is an array → replace (full snapshot from server wins)
 *   - anything else → replace
 */

export type MergeMode = "replace" | "append" | "map";

const PRIMARY_KEYS = ["gen_index", "epoch", "iter_index", "batch_index"] as const;

export function findPrimaryKey(obj: Record<string, unknown>): string | null {
  return PRIMARY_KEYS.find((k) => obj[k] !== undefined) ?? null;
}

export function appendDedupe(arr: unknown[], item: unknown): unknown[] {
  if (typeof item !== "object" || item === null || Array.isArray(item)) {
    return [...arr, item];
  }
  const key = findPrimaryKey(item as Record<string, unknown>);
  if (!key) return [...arr, item];
  const val = (item as Record<string, unknown>)[key];
  const exists = arr.some(
    (existing) =>
      typeof existing === "object" &&
      existing !== null &&
      (existing as Record<string, unknown>)[key] === val,
  );
  return exists ? arr : [...arr, item];
}

export function autoMerge(current: unknown, delta: unknown): unknown {
  if (Array.isArray(current) && !Array.isArray(delta)) {
    return appendDedupe(current, delta);
  }
  return delta;
}
