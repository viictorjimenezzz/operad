export function langfuseUrlFor(base: string, runId: string, spanId?: string): string {
  const b = base.replace(/\/$/, "");
  const url = `${b}/trace/${runId}`;
  return spanId ? `${url}?observation=${spanId}` : url;
}

export type LangfuseLinkProps = {
  href: string;
  target: "_blank";
  rel: "noopener noreferrer";
  title: string;
};

export function langfuseLinkProps(
  base: string | null | undefined,
  runId: string,
  spanId?: string | null,
): LangfuseLinkProps | null {
  if (!base) return null;
  return {
    href: langfuseUrlFor(base, runId, spanId ?? undefined),
    target: "_blank",
    rel: "noopener noreferrer",
    title: spanId ? `Open span ${spanId.slice(0, 8)} in Langfuse` : "Open trace in Langfuse",
  };
}
