/**
 * Merge semantics for data sources that combine a JSON snapshot with
 * live SSE deltas. Used by DashboardRenderer to keep one source of truth
 * (the TanStack Query cache) instead of a parallel streamed-state map.
 *
 * autoMerge heuristic:
 *   - current is an array AND delta is a non-array object -> append-dedupe
 *   - current is an object snapshot with one matching array collection
 *     AND delta is a keyed object -> append-dedupe into that collection
 *   - delta is an array -> replace (full snapshot from server wins)
 *   - anything else -> replace
 */

export type MergeMode = "replace" | "append" | "map";

const PRIMARY_KEYS = ["gen_index", "epoch", "iter_index", "round_index", "batch_index"] as const;
const ARRAY_FIELDS_BY_PRIMARY_KEY: Record<string, readonly string[]> = {
  batch_index: ["batches"],
  epoch: ["iterations"],
  gen_index: ["generations"],
  iter_index: ["iterations"],
  round_index: ["rounds"],
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
  for (const name of ARRAY_FIELDS_BY_PRIMARY_KEY[primaryKey] ?? []) {
    const value = obj[name];
    if (Array.isArray(value)) return [name, value];
  }

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
