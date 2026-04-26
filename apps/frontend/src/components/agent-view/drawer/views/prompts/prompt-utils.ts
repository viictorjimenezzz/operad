import type { AgentPromptsResponse } from "@/lib/types";

export type PromptEntry = AgentPromptsResponse["entries"][number];

export interface PromptTransition {
  index: number;
  before: PromptEntry;
  after: PromptEntry;
}

export interface ChatTurn {
  role: string;
  content: string;
}

export type PromptSectionKey = "role" | "task" | "rules" | "examples";

export const PROMPT_SECTIONS: PromptSectionKey[] = ["role", "task", "rules", "examples"];

export function promptTransitions(entries: PromptEntry[]): PromptTransition[] {
  const out: PromptTransition[] = [];
  for (let i = 1; i < entries.length; i += 1) {
    const before = entries[i - 1];
    const after = entries[i];
    if (!before || !after) continue;
    if ((before.hash_prompt ?? "") !== (after.hash_prompt ?? "")) {
      out.push({ index: i, before, after });
    }
  }
  return out;
}

export function resolveFocusedTransitionIndex(
  entries: PromptEntry[],
  transitions: PromptTransition[],
  focus: string | null,
): number {
  if (!transitions.length) return -1;
  if (!focus) return 0;
  const exact = transitions.findIndex((transition) => transition.after.invocation_id === focus);
  if (exact >= 0) return exact;
  const entryIndex = entries.findIndex((entry) => entry.invocation_id === focus);
  if (entryIndex < 0) return 0;
  let best = 0;
  let distance = Number.POSITIVE_INFINITY;
  for (let i = 0; i < transitions.length; i += 1) {
    const d = Math.abs(transitions[i]?.index ?? 0 - entryIndex);
    if (d < distance) {
      best = i;
      distance = d;
    }
  }
  return best;
}

export function parseChatTurns(text: string | null): ChatTurn[] | null {
  if (!text) return null;
  const raw = text.trim();
  if (!raw.startsWith("[") || !raw.endsWith("]")) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return null;
    const turns: ChatTurn[] = [];
    for (const item of parsed) {
      if (!item || typeof item !== "object") return null;
      const role = (item as Record<string, unknown>).role;
      const content = (item as Record<string, unknown>).content;
      if (typeof role !== "string" || typeof content !== "string") return null;
      turns.push({ role, content });
    }
    return turns;
  } catch {
    return null;
  }
}

export function extractSection(text: string | null, section: PromptSectionKey): string {
  if (!text) return "";
  const source = text.trim();
  if (!source) return "";
  const re = new RegExp(`<${section}[^>]*>([\\s\\S]*?)</${section}>`, "gi");
  const matches = [...source.matchAll(re)];
  if (matches.length) {
    return matches.map((m) => (m[1] ?? "").trim()).join("\n");
  }
  const lines = source.split("\n");
  const probe = section.toLowerCase();
  const found = lines.filter((line) => line.trim().toLowerCase().startsWith(`${probe}:`));
  if (found.length) return found.join("\n").trim();
  return "";
}

export function sectionChanges(entries: PromptEntry[]): Record<PromptSectionKey, number> {
  const out: Record<PromptSectionKey, number> = {
    role: 0,
    task: 0,
    rules: 0,
    examples: 0,
  };
  for (let i = 1; i < entries.length; i += 1) {
    const before = entries[i - 1];
    const after = entries[i];
    if (!before || !after) continue;
    for (const section of PROMPT_SECTIONS) {
      const beforeText = extractSection(before.system, section);
      const afterText = extractSection(after.system, section);
      if (beforeText !== afterText) out[section] += 1;
    }
  }
  return out;
}

export function toMarkdownBundle(entry: PromptEntry): string {
  const system = entry.system ?? "";
  const user = entry.user ?? "";
  return [
    `### invocation ${entry.invocation_id}`,
    "",
    "#### system",
    "```xml",
    system,
    "```",
    "",
    "#### user",
    "```markdown",
    user,
    "```",
  ].join("\n");
}

export function toMarkdownDiff(before: PromptEntry, after: PromptEntry): string {
  return [
    `## Prompt Diff ${before.invocation_id} -> ${after.invocation_id}`,
    "",
    "### before",
    toMarkdownBundle(before),
    "",
    "### after",
    toMarkdownBundle(after),
  ].join("\n");
}
