import { EmptyState } from "@/components/ui/empty-state";
import { MarkdownView } from "@/components/ui/markdown";
import { ExternalLink } from "lucide-react";

export interface PlanCardProps {
  attemptIndex: number | null;
  plan: unknown;
  evidence?: string[];
  retrieverHrefs?: string[];
}

export function PlanCard({
  attemptIndex,
  plan,
  evidence = [],
  retrieverHrefs = [],
}: PlanCardProps) {
  const markdown = planToMarkdown(plan);

  return (
    <section className="rounded-lg border border-border bg-bg-1 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="m-0 text-[14px] font-semibold text-text">
            {attemptIndex == null ? "Attempt unknown plan" : `Attempt #${attemptIndex + 1} plan`}
          </h2>
          <p className="m-0 mt-1 text-[11px] text-muted">Planner output</p>
        </div>
        {retrieverHrefs.length > 0 ? (
          <div className="flex flex-wrap justify-end gap-1.5">
            {retrieverHrefs.map((href, index) => (
              <a
                key={href}
                className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-[11px] text-text transition-colors hover:border-border-strong hover:bg-bg-2"
                href={href}
              >
                <ExternalLink size={12} />
                Retriever {index + 1}
              </a>
            ))}
          </div>
        ) : null}
      </div>

      {markdown ? (
        <MarkdownView value={markdown} />
      ) : (
        <EmptyState
          title="plan not available"
          description="this run predates the AutoResearcher plan event"
          className="min-h-28"
        />
      )}

      <div className="mt-4 border-t border-border pt-3">
        <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-muted">
          Retrieved evidence
        </div>
        {evidence.length > 0 ? (
          <ul className="m-0 flex list-disc flex-col gap-1 pl-4 text-[12px] leading-5 text-text/80">
            {evidence.slice(0, 6).map((item, index) => (
              <li key={`${item}-${index}`}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="m-0 text-[12px] text-muted">
            No retrieved evidence summary is attached to this plan payload.
          </p>
        )}
      </div>
    </section>
  );
}

function planToMarkdown(plan: unknown): string {
  if (typeof plan === "string") return plan;
  if (!plan || typeof plan !== "object") return "";
  return flattenObject(plan as Record<string, unknown>)
    .map(([key, value]) => `- **${key}:** ${formatValue(value)}`)
    .join("\n");
}

function flattenObject(obj: Record<string, unknown>, prefix = ""): Array<[string, unknown]> {
  const rows: Array<[string, unknown]> = [];
  for (const [key, value] of Object.entries(obj)) {
    const nextKey = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object" && !Array.isArray(value)) {
      rows.push(...flattenObject(value as Record<string, unknown>, nextKey));
    } else {
      rows.push([nextKey, value]);
    }
  }
  return rows;
}

function formatValue(value: unknown): string {
  if (value == null) return "n/a";
  if (Array.isArray(value)) return value.map(formatValue).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
