import { formatCost, formatTokens } from "@/lib/utils";

function finiteNumber(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function hasTokenUsage(
  prompt: number | null | undefined,
  completion: number | null | undefined,
): boolean {
  return (finiteNumber(prompt) ? prompt : 0) + (finiteNumber(completion) ? completion : 0) > 0;
}

export function formatTokenPairOrUnavailable(
  prompt: number | null | undefined,
  completion: number | null | undefined,
): string {
  if (!hasTokenUsage(prompt, completion)) return "unavailable";
  return `${formatTokens(prompt ?? 0)} / ${formatTokens(completion ?? 0)}`;
}

export function formatTokensOrUnavailable(total: number | null | undefined): string {
  return finiteNumber(total) && total > 0 ? formatTokens(total) : "unavailable";
}

export function formatCostOrUnavailable(cost: number | null | undefined): string {
  return finiteNumber(cost) ? formatCost(cost) : "unavailable";
}
