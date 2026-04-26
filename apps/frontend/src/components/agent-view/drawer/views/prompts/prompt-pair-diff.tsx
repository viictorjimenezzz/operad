import { cn } from "@/lib/utils";
import type { ChatTurn } from "@/components/agent-view/drawer/views/prompts/prompt-utils";
import { parseChatTurns } from "@/components/agent-view/drawer/views/prompts/prompt-utils";

interface PromptPairDiffProps {
  before: string | null;
  after: string | null;
  mode: "side-by-side" | "inline";
}

type TokenDiff = { text: string; type: "add" | "remove" | "same" };

export function PromptPairDiff({ before, after, mode }: PromptPairDiffProps) {
  const left = before ?? "";
  const right = after ?? "";
  const chatBefore = parseChatTurns(before);
  const chatAfter = parseChatTurns(after);
  if (chatBefore && chatAfter) {
    return <ChatDiff before={chatBefore} after={chatAfter} mode={mode} />;
  }

  const strategy = chooseDiffStrategy(left, right);
  if (mode === "inline") {
    if (strategy === "line") {
      const inline = inlineLineDiff(left, right);
      return (
        <pre className="m-0 overflow-auto whitespace-pre-wrap rounded border border-border bg-bg-2 p-3 text-[11px]">
          {inline.map((line, index) => (
            <div
              key={`inline-${index}`}
              className={cn(
                line.type === "add" && "bg-green-900/30 text-green-300",
                line.type === "remove" && "bg-red-900/30 text-red-300",
              )}
            >
              {line.prefix}
              {line.text || "\u00a0"}
            </div>
          ))}
        </pre>
      );
    }

    const inlineWords = inlineWordDiff(left, right);
    return (
      <div className="overflow-auto rounded border border-border bg-bg-2 p-3 text-[11px] leading-5">
        {inlineWords.map((part, index) => (
          <span
            key={`w-${index}`}
            className={cn(
              part.type === "add" && "rounded bg-green-900/30 text-green-300",
              part.type === "remove" && "rounded bg-red-900/30 text-red-300 line-through",
            )}
          >
            {part.text}
          </span>
        ))}
      </div>
    );
  }

  if (strategy === "line") {
    const leftLines = sideBySideLineDiff(left, right, "left");
    const rightLines = sideBySideLineDiff(left, right, "right");
    return (
      <div className="grid gap-2 md:grid-cols-2">
        <DiffPane label="before" lines={leftLines} />
        <DiffPane label="after" lines={rightLines} />
      </div>
    );
  }

  const leftWords = sideBySideWordDiff(left, right, "left");
  const rightWords = sideBySideWordDiff(left, right, "right");

  return (
    <div className="grid gap-2 md:grid-cols-2">
      <WordPane label="before" parts={leftWords} />
      <WordPane label="after" parts={rightWords} />
    </div>
  );
}

function DiffPane({
  label,
  lines,
}: {
  label: string;
  lines: Array<{ text: string; type: "add" | "remove" | "same" }>;
}) {
  return (
    <div className="min-w-0">
      <div className="mb-1 text-[10px] uppercase tracking-[0.08em] text-muted">{label}</div>
      <pre className="m-0 overflow-auto whitespace-pre-wrap rounded border border-border bg-bg-2 p-2 text-[11px]">
        {lines.map((line, index) => (
          <div
            key={`${label}-${index}`}
            className={cn(
              line.type === "add" && "bg-green-900/30 text-green-300",
              line.type === "remove" && "bg-red-900/30 text-red-300",
            )}
          >
            {line.text || "\u00a0"}
          </div>
        ))}
      </pre>
    </div>
  );
}

function WordPane({ label, parts }: { label: string; parts: TokenDiff[] }) {
  return (
    <div className="min-w-0">
      <div className="mb-1 text-[10px] uppercase tracking-[0.08em] text-muted">{label}</div>
      <div className="overflow-auto rounded border border-border bg-bg-2 p-2 text-[11px] leading-5">
        {parts.map((part, index) => (
          <span
            key={`${label}-w-${index}`}
            className={cn(
              part.type === "add" && "rounded bg-green-900/30 text-green-300",
              part.type === "remove" && "rounded bg-red-900/30 text-red-300",
            )}
          >
            {part.text}
          </span>
        ))}
      </div>
    </div>
  );
}

function ChatDiff({
  before,
  after,
  mode,
}: {
  before: ChatTurn[];
  after: ChatTurn[];
  mode: "side-by-side" | "inline";
}) {
  const max = Math.max(before.length, after.length);
  const rows = Array.from({ length: max }).map((_, index) => ({
    before: before[index] ?? null,
    after: after[index] ?? null,
  }));

  if (mode === "inline") {
    return (
      <div className="space-y-2">
        {rows.map((row, index) => (
          <div key={`chat-inline-${index}`} className="rounded border border-border bg-bg-2 p-2 text-[11px]">
            <div className="mb-1 uppercase tracking-[0.08em] text-muted">
              turn {index + 1} · {(row.after ?? row.before)?.role ?? "unknown"}
            </div>
            <div className="leading-5">{inlineWordDiff(row.before?.content ?? "", row.after?.content ?? "").map(renderWord)}</div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-2 md:grid-cols-2">
      <div className="space-y-2">
        <div className="text-[10px] uppercase tracking-[0.08em] text-muted">before</div>
        {rows.map((row, index) => (
          <div key={`chat-before-${index}`} className="rounded border border-border bg-bg-2 p-2 text-[11px]">
            <div className="mb-1 uppercase tracking-[0.08em] text-muted">
              {(row.before ?? row.after)?.role ?? "unknown"}
            </div>
            <div className="leading-5">{sideBySideWordDiff(row.before?.content ?? "", row.after?.content ?? "", "left").map(renderWord)}</div>
          </div>
        ))}
      </div>
      <div className="space-y-2">
        <div className="text-[10px] uppercase tracking-[0.08em] text-muted">after</div>
        {rows.map((row, index) => (
          <div key={`chat-after-${index}`} className="rounded border border-border bg-bg-2 p-2 text-[11px]">
            <div className="mb-1 uppercase tracking-[0.08em] text-muted">
              {(row.after ?? row.before)?.role ?? "unknown"}
            </div>
            <div className="leading-5">{sideBySideWordDiff(row.before?.content ?? "", row.after?.content ?? "", "right").map(renderWord)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function renderWord(part: TokenDiff, index: number) {
  return (
    <span
      key={`word-${index}`}
      className={cn(
        part.type === "add" && "rounded bg-green-900/30 text-green-300",
        part.type === "remove" && "rounded bg-red-900/30 text-red-300",
      )}
    >
      {part.text}
    </span>
  );
}

function chooseDiffStrategy(before: string, after: string): "word" | "line" {
  const combined = `${before}\n${after}`.toLowerCase();
  if (
    combined.includes("<rules") ||
    combined.includes("<examples") ||
    combined.split("\n").length > 8
  ) {
    return "line";
  }
  return "word";
}

function tokenizeWords(text: string): string[] {
  const matches = text.match(/\s+|[^\s]+/g);
  return matches ?? [];
}

function tokenizeLines(text: string): string[] {
  return text.split("\n");
}

function lcsDiff(before: string[], after: string[]): Array<{ kind: "same" | "remove" | "add"; value: string }> {
  const dp = Array.from({ length: before.length + 1 }, () => Array(after.length + 1).fill(0));
  for (let i = before.length - 1; i >= 0; i -= 1) {
    for (let j = after.length - 1; j >= 0; j -= 1) {
      const row = dp[i];
      const down = dp[i + 1]?.[j] ?? 0;
      const right = dp[i]?.[j + 1] ?? 0;
      const diag = dp[i + 1]?.[j + 1] ?? 0;
      if (!row) continue;
      if (before[i] === after[j]) row[j] = diag + 1;
      else row[j] = Math.max(down, right);
    }
  }

  const out: Array<{ kind: "same" | "remove" | "add"; value: string }> = [];
  let i = 0;
  let j = 0;
  while (i < before.length && j < after.length) {
    if (before[i] === after[j]) {
      out.push({ kind: "same", value: before[i] ?? "" });
      i += 1;
      j += 1;
      continue;
    }
    const down = dp[i + 1]?.[j] ?? 0;
    const right = dp[i]?.[j + 1] ?? 0;
    if (down >= right) {
      out.push({ kind: "remove", value: before[i] ?? "" });
      i += 1;
      continue;
    }
    out.push({ kind: "add", value: after[j] ?? "" });
    j += 1;
  }
  while (i < before.length) {
    out.push({ kind: "remove", value: before[i] ?? "" });
    i += 1;
  }
  while (j < after.length) {
    out.push({ kind: "add", value: after[j] ?? "" });
    j += 1;
  }
  return out;
}

function inlineWordDiff(before: string, after: string): TokenDiff[] {
  return lcsDiff(tokenizeWords(before), tokenizeWords(after)).map((item) => ({
    text: item.value,
    type: item.kind === "same" ? "same" : item.kind,
  }));
}

function sideBySideWordDiff(before: string, after: string, side: "left" | "right"): TokenDiff[] {
  return lcsDiff(tokenizeWords(before), tokenizeWords(after))
    .filter((item) => {
      if (item.kind === "same") return true;
      if (side === "left") return item.kind === "remove";
      return item.kind === "add";
    })
    .map((item) => ({
      text: item.value,
      type:
        item.kind === "same"
          ? "same"
          : item.kind === "remove"
            ? "remove"
            : "add",
    }));
}

function inlineLineDiff(before: string, after: string): Array<{ prefix: string; text: string; type: "add" | "remove" | "same" }> {
  return lcsDiff(tokenizeLines(before), tokenizeLines(after)).map((item) => {
    if (item.kind === "same") return { prefix: "  ", text: item.value, type: "same" as const };
    if (item.kind === "remove") return { prefix: "- ", text: item.value, type: "remove" as const };
    return { prefix: "+ ", text: item.value, type: "add" as const };
  });
}

function sideBySideLineDiff(
  before: string,
  after: string,
  side: "left" | "right",
): Array<{ text: string; type: "add" | "remove" | "same" }> {
  return lcsDiff(tokenizeLines(before), tokenizeLines(after))
    .filter((item) => {
      if (item.kind === "same") return true;
      if (side === "left") return item.kind === "remove";
      return item.kind === "add";
    })
    .map((item) => {
      const type: "add" | "remove" | "same" =
        item.kind === "same" ? "same" : item.kind === "remove" ? "remove" : "add";
      return { text: item.value, type };
    });
}

export const _promptPairDiff = {
  chooseDiffStrategy,
  parseChatTurns,
  inlineWordDiff,
  inlineLineDiff,
  sideBySideWordDiff,
  sideBySideLineDiff,
};
