import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { useMemo, useState } from "react";
import type { ChatTurn, PromptEntry, PromptSectionKey } from "@/components/agent-view/drawer/views/prompts/prompt-utils";
import { PROMPT_SECTIONS, extractSection, parseChatTurns } from "@/components/agent-view/drawer/views/prompts/prompt-utils";

interface PromptRendererProps {
  entry: PromptEntry;
  defaultRenderer: string;
  className?: string;
}

const RENDERERS = ["xml", "markdown", "chat"] as const;
type RendererMode = (typeof RENDERERS)[number];
type PromptPart = "system" | "user";

export function PromptRenderer({ entry, defaultRenderer, className }: PromptRendererProps) {
  const seedRenderer: RendererMode =
    defaultRenderer === "chat" || defaultRenderer === "xml" || defaultRenderer === "markdown"
      ? defaultRenderer
      : "markdown";
  const [renderer, setRenderer] = useState<RendererMode>(seedRenderer);
  const [part, setPart] = useState<PromptPart>("system");

  const text = part === "system" ? entry.system : entry.user;
  const chatTurns = useMemo(() => parseChatTurns(text), [text]);

  return (
    <div className={cn("rounded border border-border bg-bg-1", className)}>
      <Tabs value={part} onValueChange={(value) => setPart(value === "user" ? "user" : "system")}>
        <TabsList>
          <TabsTrigger value="system">system</TabsTrigger>
          <TabsTrigger value="user">user</TabsTrigger>
        </TabsList>
      </Tabs>
      <div className="flex items-center gap-1 border-b border-border px-2 py-1.5">
        {RENDERERS.map((mode) => (
          <button
            key={mode}
            type="button"
            className={cn(
              "rounded border px-2 py-0.5 text-[11px]",
              renderer === mode
                ? "border-accent bg-accent-dim text-text"
                : "border-border bg-bg-2 text-muted",
            )}
            onClick={() => setRenderer(mode)}
          >
            {mode}
          </button>
        ))}
      </div>
      <Tabs value={part}>
        <TabsContent value="system" className="m-0">
          <PromptBody text={text} renderer={renderer} chatTurns={chatTurns} />
        </TabsContent>
        <TabsContent value="user" className="m-0">
          <PromptBody text={text} renderer={renderer} chatTurns={chatTurns} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function PromptBody({
  text,
  renderer,
  chatTurns,
}: {
  text: string | null;
  renderer: RendererMode;
  chatTurns: ChatTurn[] | null;
}) {
  if (!text) {
    return <p className="m-0 p-3 text-[11px] text-muted">no prompt text available</p>;
  }
  if (renderer === "chat") {
    if (!chatTurns) {
      return (
        <div className="p-3 text-[11px] text-muted">
          chat parse unavailable, showing raw text
          <pre className="mt-2 overflow-auto whitespace-pre-wrap rounded border border-border bg-bg-2 p-2 text-[11px] text-text">
            {text}
          </pre>
        </div>
      );
    }
    return (
      <div className="space-y-2 p-3">
        {chatTurns.map((turn, index) => (
          <div key={`${turn.role}-${index}`} className="rounded border border-border bg-bg-2 p-2">
            <div className="mb-1 text-[10px] uppercase tracking-[0.08em] text-muted">{turn.role}</div>
            <div className="whitespace-pre-wrap font-mono text-[11px] text-text">{turn.content}</div>
          </div>
        ))}
      </div>
    );
  }
  if (renderer === "xml") {
    return <XmlPrompt text={text} />;
  }
  return (
    <pre className="m-0 overflow-auto whitespace-pre-wrap p-3 text-[11px] text-text">{text}</pre>
  );
}

function XmlPrompt({ text }: { text: string }) {
  const sections = PROMPT_SECTIONS.map((section) => ({ section, text: extractSection(text, section) })).filter(
    (entry) => entry.text.length > 0,
  );

  if (sections.length === 0) {
    return (
      <pre className="m-0 overflow-auto whitespace-pre-wrap p-3 font-mono text-[11px] text-text">
        {text}
      </pre>
    );
  }

  return (
    <div className="space-y-2 p-3">
      {sections.map((entry) => (
        <details key={entry.section} open={entry.section === "role" || entry.section === "task"}>
          <summary className="cursor-pointer text-[11px] uppercase tracking-[0.08em] text-muted">
            {entry.section}
          </summary>
          <XmlBlock text={entry.text} section={entry.section} />
        </details>
      ))}
    </div>
  );
}

function XmlBlock({ text, section }: { text: string; section: PromptSectionKey }) {
  const lines = text.split("\n");
  return (
    <pre className="mt-1 overflow-auto whitespace-pre-wrap rounded border border-border bg-bg-2 p-2 font-mono text-[11px] text-text">
      <span className="text-accent">{`<${section}>`}</span>
      {"\n"}
      {lines.map((line, index) => (
        <span key={`${section}-${index}`}>
          {line}
          {index < lines.length - 1 ? "\n" : ""}
        </span>
      ))}
      {"\n"}
      <span className="text-accent">{`</${section}>`}</span>
    </pre>
  );
}
