import { InvokeButton } from "@/components/agent-view/drawer/views/experiment/invoke-button";
import { PromptEditor } from "@/components/agent-view/drawer/views/experiment/prompt-editor";
import { ResultCard, type ExperimentResult } from "@/components/agent-view/drawer/views/experiment/result-card";
import { EmptyState } from "@/components/ui/empty-state";
import { dashboardApi, HttpError } from "@/lib/api/dashboard";
import type { AgentMetaResponse } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

interface ExperimentRunnerProps {
  runId: string;
  agentPath: string;
  initialInput?: unknown;
}

function asObject(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return value as Record<string, unknown>;
}

function stringifyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function parseExamples(raw: string): Array<{ input: unknown; output: unknown }> | null {
  const text = raw.trim();
  if (!text) return [];
  const parsed = JSON.parse(text) as unknown;
  if (!Array.isArray(parsed)) throw new Error("examples must be a JSON array");
  return parsed.map((entry) => {
    const obj = asObject(entry);
    return {
      input: obj.input,
      output: obj.output,
    };
  });
}

function defaultsFromMeta(meta: AgentMetaResponse | undefined) {
  const role = meta?.role ?? "";
  const task = meta?.task ?? "";
  const rulesText = (meta?.rules ?? []).join("\n");
  const examplesText = stringifyJson(meta?.examples ?? []);
  const temperature = meta?.config?.sampling?.temperature;
  const temperatureText = typeof temperature === "number" ? String(temperature) : "";
  return { role, task, rulesText, examplesText, temperatureText };
}

export function ExperimentRunner({ runId, agentPath, initialInput }: ExperimentRunnerProps) {
  const metaQuery = useQuery({
    queryKey: ["run", "agent-meta", runId, agentPath] as const,
    queryFn: () => dashboardApi.agentMeta(runId, agentPath),
    enabled: runId.length > 0 && agentPath.length > 0,
    staleTime: 10_000,
  });
  const invocationsQuery = useQuery({
    queryKey: ["run", "agent-invocations", runId, agentPath] as const,
    queryFn: () => dashboardApi.agentInvocations(runId, agentPath),
    enabled: runId.length > 0 && agentPath.length > 0,
    staleTime: 10_000,
  });

  const defaults = useMemo(() => defaultsFromMeta(metaQuery.data), [metaQuery.data]);
  const [editor, setEditor] = useState(defaults);
  const [inputMode, setInputMode] = useState<"historic" | "manual">(
    initialInput ? "manual" : "historic",
  );
  const [selectedInvocationId, setSelectedInvocationId] = useState<string>("");
  const [manualInputText, setManualInputText] = useState(stringifyJson(initialInput ?? {}));
  const [compare, setCompare] = useState(false);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<ExperimentResult[]>([]);

  useEffect(() => {
    setEditor(defaults);
  }, [defaults]);

  const invocations = invocationsQuery.data?.invocations ?? [];

  const historicalInput = useMemo(() => {
    const match = invocations.find((row) => row.id === selectedInvocationId) ?? invocations.at(-1);
    return asObject(match?.input);
  }, [invocations, selectedInvocationId]);

  const effectiveInputText = inputMode === "manual" ? manualInputText : stringifyJson(historicalInput);

  const currentInput = (): Record<string, unknown> => {
    if (inputMode === "manual") {
      const parsed = JSON.parse(manualInputText) as unknown;
      return asObject(parsed);
    }
    return historicalInput;
  };

  const buildOverrides = () => {
    const out: Record<string, unknown> = {};
    if (editor.role.trim() !== defaults.role.trim()) out.role = editor.role;
    if (editor.task.trim() !== defaults.task.trim()) out.task = editor.task;
    if (editor.rulesText.trim() !== defaults.rulesText.trim()) {
      out.rules = editor.rulesText
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
    }
    if (editor.examplesText.trim() !== defaults.examplesText.trim()) {
      out.examples = parseExamples(editor.examplesText);
    }
    if (editor.temperatureText.trim() !== defaults.temperatureText.trim()) {
      const n = Number(editor.temperatureText);
      if (!Number.isFinite(n)) throw new Error("temperature must be a number");
      out.config = { sampling: { temperature: n } };
    }
    return out;
  };

  const onRun = async () => {
    if (running) return;
    setRunning(true);
    const startedAt = Date.now();
    try {
      const input = currentInput();
      const overrides = buildOverrides();
      const experimentBody = {
        input,
        stream: false,
        ...(Object.keys(overrides).length > 0 ? { overrides } : {}),
      };

      if (compare) {
        const [experiment, live] = await Promise.all([
          dashboardApi.agentInvoke(runId, agentPath, experimentBody),
          dashboardApi.agentInvoke(runId, agentPath, { input, stream: false }),
        ]);
        setResults((prev) => [
          {
            id: `${startedAt}`,
            startedAt,
            input,
            compare: true,
            experiment,
            live,
          },
          ...prev,
        ]);
      } else {
        const experiment = await dashboardApi.agentInvoke(runId, agentPath, experimentBody);
        setResults((prev) => [
          {
            id: `${startedAt}`,
            startedAt,
            input,
            compare: false,
            experiment,
          },
          ...prev,
        ]);
      }
    } catch (error) {
      const reason =
        error instanceof HttpError
          ? `HTTP ${error.status}: ${error.message}`
          : error instanceof Error
            ? error.message
            : "run failed";
      const input = (() => {
        try {
          return currentInput();
        } catch {
          return {};
        }
      })();
      setResults((prev) => [
        {
          id: `${startedAt}`,
          startedAt,
          input,
          compare,
          error: reason,
        },
        ...prev,
      ]);
    } finally {
      setRunning(false);
    }
  };

  if (metaQuery.isPending || invocationsQuery.isPending) {
    return <EmptyState title="loading experiment" description="fetching agent metadata and history" />;
  }

  if (metaQuery.isError) {
    return <EmptyState title="agent metadata unavailable" />;
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-3">
      <PromptEditor
        role={editor.role}
        task={editor.task}
        rulesText={editor.rulesText}
        examplesText={editor.examplesText}
        temperatureText={editor.temperatureText}
        defaults={defaults}
        onChange={setEditor}
      />

      <div className="space-y-2 rounded border border-border bg-bg-1 p-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">input picker</div>
        <div className="flex items-center gap-3 text-xs">
          <label className="flex items-center gap-1">
            <input
              type="radio"
              checked={inputMode === "historic"}
              onChange={() => setInputMode("historic")}
            />
            use historic input
          </label>
          <label className="flex items-center gap-1">
            <input
              type="radio"
              checked={inputMode === "manual"}
              onChange={() => setInputMode("manual")}
            />
            type my own
          </label>
        </div>

        {inputMode === "historic" ? (
          <select
            className="w-full rounded border border-border bg-bg-2 p-2 text-xs"
            value={selectedInvocationId}
            onChange={(e) => setSelectedInvocationId(e.target.value)}
          >
            <option value="">latest invocation</option>
            {invocations.map((row, index) => (
              <option key={row.id} value={row.id}>
                #{index + 1} · {row.id}
              </option>
            ))}
          </select>
        ) : null}

        <textarea
          className="w-full rounded border border-border bg-bg-2 p-2 font-mono text-xs text-text"
          rows={8}
          value={effectiveInputText}
          onChange={(e) => {
            if (inputMode === "manual") setManualInputText(e.target.value);
          }}
          readOnly={inputMode !== "manual"}
        />
      </div>

      <div className="flex items-center gap-3 rounded border border-border bg-bg-1 p-3">
        <label className="flex items-center gap-2 text-xs">
          <input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} />
          compare with live baseline
        </label>
        <div className="ml-auto">
          <InvokeButton running={running} onRun={onRun} />
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-2 overflow-auto">
        {results.length === 0 ? (
          <EmptyState title="no experiment runs yet" description="edit, pick input, then run" />
        ) : (
          results.map((result) => <ResultCard key={result.id} result={result} />)
        )}
      </div>
    </div>
  );
}
