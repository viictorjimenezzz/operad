import { PromptTracebackReader } from "@/components/algorithms/trainer/prompt-traceback-reader";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function wrapper(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

function mockFetchWithFrames() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/manifest") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            mode: "development",
            langfuseUrl: "http://lf.example",
          }),
        } satisfies Partial<Response>;
      }
      if (url === "/runs/trainer-1/traceback.ndjson") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            frames: [
              {
                agent_path: "research_analyst.stage_2.role",
                input: { question: "q3" },
                output: { answer: "a3" },
                rendered_prompt: "prompt-three",
                gradient: {
                  message: "third frame message",
                  severity: "high",
                  optimizer: "TextualGradientDescent",
                  optimizer_step: 7,
                  critic: { run_id: "critic-3" },
                },
              },
              {
                agent_path: "research_analyst.stage_1.role",
                gradient: {
                  message: "second frame message",
                  severity: "medium",
                  optimizer: "TextualGradientDescent",
                  optimizer_step: 6,
                },
              },
              {
                agent_path: "research_analyst.stage_0.role",
                rendered_prompt: "prompt-one",
                gradient: {
                  message: "first frame message",
                  severity: "low",
                  optimizer: "TextualGradientDescent",
                  optimizer_step: 5,
                },
              },
            ],
          }),
        } satisfies Partial<Response>;
      }
      throw new Error(`unexpected fetch URL: ${url}`);
    }),
  );
}

describe("PromptTracebackReader", () => {
  it("renders frames newest-first with frame metadata", async () => {
    mockFetchWithFrames();

    render(wrapper(<PromptTracebackReader runId="trainer-1" />));

    const labels = await screen.findAllByText(/frame #/i);
    expect(labels.map((label) => label.textContent)).toEqual(["frame #3", "frame #2", "frame #1"]);
    expect(screen.getByText("research_analyst.stage_2.role")).toBeTruthy();
    expect(screen.getByText("step 7")).toBeTruthy();
    expect(screen.getByText("langfuse ->")).toBeTruthy();
  });

  it("expands prompt and io content", async () => {
    mockFetchWithFrames();

    render(wrapper(<PromptTracebackReader runId="trainer-1" />));

    expect(await screen.findByText("frame #3")).toBeTruthy();
    expect(screen.queryByText("prompt-three")).toBeNull();
    expect(screen.queryByText(/^input$/i)).toBeNull();

    fireEvent.click(screen.getAllByRole("button", { name: /expand prompt \+ i\/o/i })[0]!);
    expect(await screen.findByText("prompt-three")).toBeTruthy();
    expect(screen.getByText(/^input$/i)).toBeTruthy();
  });

  it("shows required empty state when traceback is missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/manifest") {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              mode: "development",
              langfuseUrl: null,
            }),
          } satisfies Partial<Response>;
        }
        if (url === "/runs/trainer-404/traceback.ndjson") {
          return {
            ok: false,
            status: 404,
            statusText: "Not Found",
            json: async () => ({ detail: "no traceback for this run" }),
          } satisfies Partial<Response>;
        }
        throw new Error(`unexpected fetch URL: ${url}`);
      }),
    );

    render(wrapper(<PromptTracebackReader runId="trainer-404" />));

    expect(await screen.findByText("no traceback recorded")).toBeTruthy();
    expect(
      screen.getByText(
        "this run did not save a PromptTraceback; add ptb.PromptTraceback.from_run(...).save(path) to your training script",
      ),
    ).toBeTruthy();
  });
});
