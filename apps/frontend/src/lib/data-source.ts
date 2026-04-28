/**
 * Merge semantics for data sources that combine a JSON snapshot with
 * live SSE deltas. Used by DashboardRenderer to keep one source of truth
 * (the TanStack Query cache) instead of a parallel streamed-state map.
 *
 * autoMerge heuristic:
 *   - current is an array AND delta is a non-array object → append-dedupe
 *   - current is an object with a matching array field AND delta is a row → append-dedupe into that field
 *   - delta is an array → replace (full snapshot from server wins)
 *   - anything else → replace
 */

export type MergeMode = "replace" | "append" | "map";

const PRIMARY_KEYS = ["gen_index", "epoch", "iter_index", "batch_index"] as const;
const ARRAY_FIELDS_BY_PRIMARY_KEY: Record<string, readonly string[]> = {
  batch_index: ["batches"],
  epoch: ["iterations"],
  gen_index: ["generations"],
  iter_index: ["iterations"],
};

export function findPrimaryKey(obj: Record<string, unknown>): string | null {
  return PRIMARY_KEYS.find((k) => obj[k] !== undefined) ?? null;
}

export function appendDedupe(arr: unknown[], item: unknown): unknown[] {
  if (!isRecord(item)) {
    return [...arr, item];
  }
  const key = findPrimaryKey(item);
  if (!key) return [...arr, item];
  const exists = arr.some((existing) => isRecord(existing) && sameRowIdentity(existing, item, key));
  return exists ? arr : [...arr, item];
}

export function autoMerge(current: unknown, delta: unknown): unknown {
  if (Array.isArray(current) && !Array.isArray(delta)) {
    return appendDedupe(current, delta);
  }
  if (isRecord(current) && isRecord(delta)) {
    const arrayField = arrayFieldForDelta(current, delta);
    if (arrayField) {
      return {
        ...current,
        [arrayField]: appendDedupe(current[arrayField] as unknown[], delta),
      };
    }
  }
  return delta;
}

function arrayFieldForDelta(
  current: Record<string, unknown>,
  delta: Record<string, unknown>,
): string | null {
  const key = findPrimaryKey(delta);
  if (!key) return null;

  for (const field of ARRAY_FIELDS_BY_PRIMARY_KEY[key] ?? []) {
    if (Array.isArray(current[field])) return field;
  }

  const arrayFields = Object.entries(current)
    .filter(([, value]) => Array.isArray(value))
    .map(([field]) => field);
  return arrayFields.length === 1 ? (arrayFields[0] ?? null) : null;
}

function sameRowIdentity(
  existing: Record<string, unknown>,
  item: Record<string, unknown>,
  key: string,
): boolean {
  if (existing[key] !== item[key]) return false;

  if (key !== "iter_index") return true;
  const itemPhase = typeof item.phase === "string" ? item.phase : null;
  const existingPhase = typeof existing.phase === "string" ? existing.phase : null;
  if (itemPhase !== null) return existingPhase === itemPhase;
  return existingPhase === null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
