import { Button, Eyebrow, FieldTree } from "@/components/ui";
import { useAgentMeta } from "@/hooks/use-runs";
import { dashboardApi } from "@/lib/api/dashboard";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useEffect, useState } from "react";

export function TabExperiment({ runId, agentPath }: { runId: string; agentPath: string }) {
  const meta = useAgentMeta(runId, agentPath);
  const invocationsQuery = useQuery({
    queryKey: ["agent-invocations-tab", runId, agentPath] as const,
    queryFn: () => dashboardApi.agentInvocations(runId, agentPath),
    staleTime: 30_000,
  });

  const [role, setRole] = useState("");
  const [task, setTask] = useState("");
  const [rulesText, setRulesText] = useState("");
  const [inputJson, setInputJson] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<unknown>(null);

  useEffect(() => {
    if (!meta.data) return;
    setRole(meta.data.role ?? "");
    setTask(meta.data.task ?? "");
    setRulesText(meta.data.rules.join("\n"));
  }, [meta.data]);

  useEffect(() => {
    const inv = invocationsQuery.data?.invocations.at(-1);
    if (inv?.input !== undefined && inv.input !== null) {
      try {
        setInputJson(JSON.stringify(inv.input, null, 2));
      } catch {
        setInputJson("");
      }
    }
  }, [invocationsQuery.data]);

  const invokeMutation = useMutation({
    mutationFn: async () => {
      let parsed: Record<string, unknown> = {};
      if (inputJson.trim()) {
        try {
          const next = JSON.parse(inputJson) as unknown;
          if (next && typeof next === "object" && !Array.isArray(next)) {
            parsed = next as Record<string, unknown>;
          } else {
            throw new Error("input JSON must be an object");
          }
        } catch (e) {
          throw new Error(`invalid input JSON: ${(e as Error).message}`);
        }
      }
      const overrides: { role?: string; task?: string; rules?: string[] } = {};
      if (role !== (meta.data?.role ?? "")) overrides.role = role;
      if (task !== (meta.data?.task ?? "")) overrides.task = task;
      const newRules = rulesText
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
      if (
        newRules.length !== (meta.data?.rules.length ?? 0) ||
        newRules.some((r, i) => r !== meta.data?.rules[i])
      ) {
        overrides.rules = newRules;
      }
      return dashboardApi.agentInvoke(runId, agentPath, {
        input: parsed,
        overrides,
        stream: false,
      });
    },
    onSuccess: (res) => {
      setError(null);
      setResult(res);
    },
    onError: (err) => {
      setError((err as Error).message);
      setResult(null);
    },
  });

  return (
    <div className="space-y-4 p-5">
      <section>
        <Eyebrow>role</Eyebrow>
        <textarea
          value={role}
          onChange={(e) => setRole(e.target.value)}
          rows={2}
          className="mt-1 w-full resize-y rounded-lg border border-border bg-bg-2 px-3 py-2 font-mono text-[12px] text-text outline-none focus:border-accent"
        />
      </section>
      <section>
        <Eyebrow>task</Eyebrow>
        <textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          rows={3}
          className="mt-1 w-full resize-y rounded-lg border border-border bg-bg-2 px-3 py-2 font-mono text-[12px] text-text outline-none focus:border-accent"
        />
      </section>
      <section>
        <Eyebrow>rules (one per line)</Eyebrow>
        <textarea
          value={rulesText}
          onChange={(e) => setRulesText(e.target.value)}
          rows={4}
          className="mt-1 w-full resize-y rounded-lg border border-border bg-bg-2 px-3 py-2 font-mono text-[12px] text-text outline-none focus:border-accent"
        />
      </section>
      <section>
        <Eyebrow>input (json)</Eyebrow>
        <textarea
          value={inputJson}
          onChange={(e) => setInputJson(e.target.value)}
          rows={5}
          className="mt-1 w-full resize-y rounded-lg border border-border bg-bg-2 px-3 py-2 font-mono text-[12px] text-text outline-none focus:border-accent"
        />
      </section>

      <div className="flex items-center gap-2">
        <Button
          variant="primary"
          onClick={() => invokeMutation.mutate()}
          disabled={invokeMutation.isPending}
          className="gap-1.5"
        >
          <Play size={12} />
          {invokeMutation.isPending ? "running…" : "run"}
        </Button>
        {error ? <span className="font-mono text-[11px] text-[--color-err]">{error}</span> : null}
      </div>

      {result ? (
        <section className="rounded-xl border border-border bg-bg-inset p-3">
          <Eyebrow>result</Eyebrow>
          <div className="mt-2">
            <FieldTree data={result} defaultDepth={2} />
          </div>
        </section>
      ) : null}
    </div>
  );
}
