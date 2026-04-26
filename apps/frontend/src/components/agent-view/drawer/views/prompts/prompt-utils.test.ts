import {
  parseChatTurns,
  promptTransitions,
  resolveFocusedTransitionIndex,
  sectionChanges,
  toMarkdownDiff,
  type PromptEntry,
} from "@/components/agent-view/drawer/views/prompts/prompt-utils";
import { describe, expect, it } from "vitest";

function entry(id: string, hash: string, system: string, user = "u"): PromptEntry {
  return {
    invocation_id: id,
    started_at: 1,
    hash_prompt: hash,
    system,
    user,
    replayed: true,
  };
}

describe("prompt utils", () => {
  it("finds transitions and resolves focus", () => {
    const entries = [
      entry("a", "h1", "<role>a</role>"),
      entry("b", "h1", "<role>a</role>"),
      entry("c", "h2", "<role>b</role>"),
      entry("d", "h3", "<role>c</role>"),
    ];

    const transitions = promptTransitions(entries);
    expect(transitions).toHaveLength(2);
    expect(resolveFocusedTransitionIndex(entries, transitions, "d")).toBe(1);
    expect(resolveFocusedTransitionIndex(entries, transitions, "b")).toBe(0);
    expect(resolveFocusedTransitionIndex(entries, transitions, null)).toBe(0);
  });

  it("counts section changes", () => {
    const entries = [
      entry("a", "h1", "<role>r1</role>\n<task>t1</task>\n<rules>x</rules>"),
      entry("b", "h2", "<role>r2</role>\n<task>t1</task>\n<rules>x</rules>"),
      entry("c", "h3", "<role>r2</role>\n<task>t2</task>\n<rules>y</rules>"),
    ];
    expect(sectionChanges(entries)).toEqual({
      role: 1,
      task: 1,
      rules: 1,
      examples: 0,
    });
  });

  it("parses chat turns best effort", () => {
    expect(parseChatTurns('[{"role":"system","content":"x"}]')).toEqual([
      { role: "system", content: "x" },
    ]);
    expect(parseChatTurns("not-json")).toBeNull();
  });

  it("builds markdown diff", () => {
    const text = toMarkdownDiff(
      entry("a", "h1", "<role>a</role>", "hello"),
      entry("b", "h2", "<role>b</role>", "world"),
    );
    expect(text).toContain("Prompt Diff a -> b");
    expect(text).toContain("<role>b</role>");
  });
});
