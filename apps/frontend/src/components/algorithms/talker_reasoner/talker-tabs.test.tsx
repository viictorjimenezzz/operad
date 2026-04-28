import { TalkerDecisionsTab } from "@/components/algorithms/talker_reasoner/decisions-tab";
import {
  TalkerTranscriptTab,
  buildTurnRows,
} from "@/components/algorithms/talker_reasoner/transcript-tab";
import { TalkerTreeTab } from "@/components/algorithms/talker_reasoner/tree-tab";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

const summary = {
  iterations: [
    {
      iter_index: 0,
      phase: "speak",
      metadata: {
        decision_kind: "talker",
        user_message: "hello",
        from_node_id: "root",
        to_node_id: "talk-node",
        router_confidence: 0.91,
      },
    },
    {
      iter_index: 1,
      phase: "speak",
      metadata: {
        decision_kind: "reasoner",
        user_message: "why",
        from_node_id: "talk-node",
        to_node_id: "reason-node",
        router_confidence: 0.42,
      },
    },
  ],
};

const events = {
  events: [
    {
      type: "algo_event",
      kind: "iteration",
      payload: {
        phase: "speak",
        iter_index: 0,
        decision_kind: "talker",
        user_message: "hello",
        from_node_id: "root",
        to_node_id: "talk-node",
        router_confidence: 0.91,
      },
    },
    {
      type: "algo_event",
      kind: "iteration",
      payload: {
        phase: "speak",
        iter_index: 1,
        decision_kind: "reasoner",
        user_message: "why",
        from_node_id: "talk-node",
        to_node_id: "reason-node",
        router_confidence: 0.42,
      },
    },
    {
      type: "agent_event",
      kind: "end",
      agent_path: "ScenarioNavigator",
      output: { response: { text: "Need more context." } },
      langfuse_url: "https://langfuse.example/trace/1",
    },
    {
      type: "agent_event",
      kind: "end",
      agent_path: "Assistant",
      output: { response: { text: "Sure, what do you want to explore?" } },
      langfuse_url: "https://langfuse.example/trace/2",
    },
    {
      type: "agent_event",
      kind: "end",
      agent_path: "ScenarioNavigator",
      output: { response: { text: "Branch to deeper reasoning." } },
      langfuse_url: "https://langfuse.example/trace/3",
    },
    {
      type: "agent_event",
      kind: "end",
      agent_path: "Assistant",
      output: { response: { text: "Here is the reasoning path." } },
      langfuse_url: "https://langfuse.example/trace/4",
    },
  ],
};

describe("TalkerReasoner tabs", () => {
  it("buildTurnRows extracts routing, transcript, and langfuse fields", () => {
    const rows = buildTurnRows(summary, events);

    expect(rows).toHaveLength(2);
    expect(rows[0]?.routerChoice).toBe("talker");
    expect(rows[0]?.routerConfidence).toBe(0.91);
    expect(rows[0]?.talkerOutput).toContain("what do you want to explore");
    expect(rows[1]?.reasonerOutput).toContain("Branch to deeper reasoning");
    expect(rows[1]?.langfuseUrl).toBe("https://langfuse.example/trace/3");
  });

  it("renders transcript as chat-style turns", () => {
    render(
      <MemoryRouter>
        <TalkerTranscriptTab dataSummary={summary} dataEvents={events} />
      </MemoryRouter>,
    );

    expect(screen.getByText("transcript")).toBeTruthy();
    expect(screen.getByText("2 turns")).toBeTruthy();
    expect(screen.getByText("hello")).toBeTruthy();
    expect(screen.getByText(/Sure, what do you want to explore/)).toBeTruthy();
  });

  it("renders tree branches and decisions table", () => {
    render(
      <MemoryRouter>
        <TalkerTreeTab dataSummary={summary} dataEvents={events} />
      </MemoryRouter>,
    );

    expect(screen.getByText("decision tree")).toBeTruthy();
    expect(screen.getAllByText("talker").length).toBeGreaterThan(0);
    expect(screen.getAllByText("reasoner").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/chosen/).length).toBeGreaterThan(0);

    cleanup();

    render(
      <MemoryRouter>
        <TalkerDecisionsTab runId="run-1" dataSummary={summary} dataEvents={events} />
      </MemoryRouter>,
    );

    expect(screen.getByText("router choice")).toBeTruthy();
    expect(screen.getByText("router confidence")).toBeTruthy();
    expect(screen.getByText("final response preview")).toBeTruthy();
    expect(screen.getAllByText("open").length).toBeGreaterThan(0);
  });
});
