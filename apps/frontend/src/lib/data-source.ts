/**
 * Merge semantics for data sources that combine a JSON snapshot with
 * live SSE deltas. Used by DashboardRenderer to keep one source of truth
 * (the TanStack Query cache) instead of a parallel streamed-state map.
 *
 * autoMerge heuristic:
 *   - current is an array AND delta is a non-array object → append-dedupe
 *   - current is an object snapshot with one matching array collection
 *     AND delta is a keyed object → append-dedupe into that collection
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
  if (isRecord(current) && isRecord(delta)) {
    const key = findPrimaryKey(delta);
    if (!key) return delta;

    const collection = findArrayCollection(current, key);
    if (!collection) return delta;

    const [name, arr] = collection;
    const next = appendDedupe(arr, delta);
    return next === arr ? current : { ...current, [name]: next };
  }
  return delta;
}

function findArrayCollection(
  obj: Record<string, unknown>,
  primaryKey: string,
): [string, unknown[]] | null {
  const arrayEntries = Object.entries(obj).filter((entry): entry is [string, unknown[]] =>
    Array.isArray(entry[1]),
  );
  const matching = arrayEntries.filter(([, arr]) =>
    arr.some((item) => isRecord(item) && findPrimaryKey(item) === primaryKey),
  );
  if (matching.length === 1) return matching[0] ?? null;
  if (matching.length > 1) return null;
  return arrayEntries.length === 1 ? (arrayEntries[0] ?? null) : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
