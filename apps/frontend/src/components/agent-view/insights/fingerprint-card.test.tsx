import { FingerprintCard } from "@/components/agent-view/insights/fingerprint-card";
import { useUIStore } from "@/stores/ui";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("FingerprintCard", () => {
  beforeEach(() => {
    useUIStore.setState({ drawer: null });
  });
  afterEach(() => cleanup());

  it("renders all 7 hash rows", () => {
    render(
      <FingerprintCard
        hashes={{
          hash_model: "m1",
          hash_prompt: "p1",
          hash_graph: "g1",
          hash_input: "i1",
          hash_output_schema: "o1",
          hash_config: "c1",
          hash_content: "k1",
        }}
      />,
    );
    expect(screen.getByText("hash_model")).toBeTruthy();
    expect(screen.getByText("hash_prompt")).toBeTruthy();
    expect(screen.getByText("hash_graph")).toBeTruthy();
    expect(screen.getByText("hash_input")).toBeTruthy();
    expect(screen.getByText("hash_output_schema")).toBeTruthy();
    expect(screen.getByText("hash_config")).toBeTruthy();
    expect(screen.getByText("hash_content")).toBeTruthy();
  });

  it("copies hash and opens find-runs drawer action", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    render(
      <FingerprintCard
        hashes={{
          hash_model: "m1",
          hash_prompt: "prompt-hash-value",
          hash_graph: "g1",
          hash_input: "i1",
          hash_output_schema: "o1",
          hash_config: "c1",
          hash_content: "k1",
        }}
      />,
    );

    const copyButtons = screen.getAllByLabelText("copy hash_prompt");
    fireEvent.click(copyButtons[copyButtons.length - 1] as Element);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("prompt-hash-value"));

    const findButtons = screen.getAllByLabelText("find runs for hash_prompt");
    fireEvent.click(findButtons[findButtons.length - 1] as Element);
    expect(useUIStore.getState().drawer).toEqual({
      kind: "find-runs",
      payload: { hash: "hash_prompt", value: "prompt-hash-value" },
    });
  });
});
