import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Loader2, Pencil, RotateCcw } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export interface MarkdownViewProps {
  value: string;
  onSave?: (next: string) => Promise<void>;
}

interface MarkdownEditorProps extends MarkdownViewProps {
  onCancel?: () => void;
}

export function MarkdownView({ value, onSave }: MarkdownViewProps) {
  const [editing, setEditing] = useState(false);

  if (editing && onSave) {
    return (
      <MarkdownEditor
        value={value}
        onSave={async (next) => {
          await onSave(next);
          setEditing(false);
        }}
        onCancel={() => setEditing(false)}
      />
    );
  }

  return (
    <div className="group relative">
      {onSave ? (
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setEditing(true)}
          className="absolute right-0 top-0 h-6 px-2 opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100"
          aria-label="edit markdown"
        >
          <Pencil size={12} />
        </Button>
      ) : null}
      <MarkdownBody value={value} {...(onSave ? { className: "pr-9" } : {})} />
    </div>
  );
}

export function MarkdownEditor({ value, onSave, onCancel }: MarkdownEditorProps) {
  const [text, setText] = useState(value);
  const [preview, setPreview] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    if (!onSave) return;
    setPending(true);
    setError(null);
    try {
      await onSave(text);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className={cn("rounded-md border border-border bg-bg-1", error && "border-[--color-err]")}>
      <div className="flex items-center justify-between gap-2 border-b border-border px-2 py-1.5">
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant={preview ? "ghost" : "default"}
            onClick={() => setPreview(false)}
            className="h-6 px-2"
          >
            Edit
          </Button>
          <Button
            size="sm"
            variant={preview ? "default" : "ghost"}
            onClick={() => setPreview(true)}
            className="h-6 px-2"
          >
            Preview
          </Button>
        </div>
        <div className="flex items-center gap-1">
          {onCancel ? (
            <Button size="sm" variant="ghost" onClick={onCancel} className="h-6 px-2">
              Cancel
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="primary"
            onClick={save}
            disabled={pending || !onSave}
            className="h-6 px-2"
          >
            {pending ? <Loader2 size={12} className="animate-spin" /> : null}
            Save
          </Button>
        </div>
      </div>
      <div className="p-2">
        {preview ? (
          <MarkdownBody value={text} />
        ) : (
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="min-h-36 w-full resize-y rounded border border-border bg-bg-inset p-2 font-mono text-[12px] leading-5 text-text outline-none focus:border-accent"
            aria-label="markdown text"
          />
        )}
        {error ? (
          <div className="mt-2 flex items-center justify-between gap-3 rounded border border-[--color-err-dim] bg-[--color-err-dim]/30 px-2 py-1.5 text-[12px] text-[--color-err]">
            <span>{error}</span>
            <Button
              size="sm"
              variant="danger"
              onClick={save}
              disabled={pending}
              className="h-6 px-2"
            >
              <RotateCcw size={12} />
              Retry
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function MarkdownBody({
  value,
  className,
}: {
  value: string;
  className?: string | undefined;
}) {
  return (
    <div
      className={cn(
        "prose prose-invert max-w-none text-[13px] leading-6 text-text",
        "[&_a]:text-accent [&_a]:underline [&_blockquote]:border-l-2 [&_blockquote]:border-border-strong [&_blockquote]:pl-3 [&_blockquote]:text-muted",
        "[&_code]:rounded [&_code]:bg-bg-inset [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[12px]",
        "[&_h1]:mb-2 [&_h1]:mt-0 [&_h1]:text-lg [&_h2]:mb-2 [&_h2]:mt-4 [&_h2]:text-base [&_h3]:mb-1 [&_h3]:mt-3 [&_h3]:text-sm",
        "[&_li]:my-1 [&_ol]:my-2 [&_ol]:pl-5 [&_p]:my-2 [&_pre]:overflow-auto [&_pre]:rounded [&_pre]:bg-bg-inset [&_pre]:p-2 [&_ul]:my-2 [&_ul]:pl-5",
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{value || "_No notes yet._"}</ReactMarkdown>
    </div>
  );
}
