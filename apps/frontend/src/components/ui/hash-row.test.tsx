import { HashRow, type HashKey } from "@/components/ui/hash-row";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

const HASH_KEYS: HashKey[] = [
  "hash_model",
  "hash_prompt",
  "hash_input",
  "hash_output_schema",
  "hash_config",
  "hash_graph",
  "hash_content",
];

function makeHashes(seed: string): Record<HashKey, string> {
  return Object.fromEntries(
    HASH_KEYS.map((key, index) => [key, `${seed}-${index.toString(16).repeat(32)}`]),
  ) as Record<HashKey, string>;
}

describe("HashRow", () => {
  it("renders seven hash chips", () => {
    render(<HashRow current={makeHashes("current")} />);
    expect(screen.getAllByRole("listitem").length).toBe(7);
  });

  it("marks changed hashes with warn outline", () => {
    const current = makeHashes("current");
    const previous = makeHashes("previous");
    previous.hash_graph = current.hash_graph;

    render(<HashRow current={current} previous={previous} />);

    const changed = screen.getByRole("listitem", { name: /hash_model hash/ });
    const unchanged = screen.getByRole("listitem", { name: /hash_graph hash/ });
    expect(changed.className.includes("border-[--color-warn]")).toBe(true);
    expect(unchanged.className.includes("border-[--color-warn]")).toBe(false);
  });

  it("shows tooltip with copy affordance and calls onCopy", async () => {
    const onCopy = vi.fn();
    const current = makeHashes("current");
    render(<HashRow current={current} onCopy={onCopy} />);

    const trigger = screen.getByRole("listitem", { name: /hash_prompt hash/ });
    fireEvent.focus(trigger);
    const copyButtons = await screen.findAllByRole("button", { name: /copy/i });
    const copyButton = copyButtons[0];
    if (!copyButton) throw new Error("missing copy button");
    fireEvent.click(copyButton);

    expect(onCopy).toHaveBeenCalledWith("hash_prompt", current.hash_prompt);
  });

  it("renders compact variant with full-hash tooltip rows", async () => {
    render(<HashRow variant="compact" current={makeHashes("current")} />);

    const trigger = screen.getByRole("button", { name: /hash drift summary/i });
    fireEvent.focus(trigger);

    expect((await screen.findAllByText(/hash_model:/i)).length).toBeGreaterThan(0);
    expect(
      (await screen.findAllByRole("button", { name: /copy hash_prompt/i })).length,
    ).toBeGreaterThan(0);
  });

  it("renders strip variant with seven drift cells", () => {
    const current = makeHashes("current");
    const previous = makeHashes("previous");
    render(<HashRow variant="strip" current={current} previous={previous} />);

    expect(screen.getByRole("list", { name: /hash drift strip/i })).toBeTruthy();
    expect(screen.getAllByRole("listitem").length).toBe(7);
  });
});
