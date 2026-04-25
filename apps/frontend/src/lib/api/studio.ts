import { HttpError, ParseError } from "@/lib/api/dashboard";
import { JobDetailResponse, JobSummary, Manifest } from "@/lib/types";
/**
 * Typed fetch wrappers for the studio FastAPI. The new /jobs and
 * /jobs/{name}/rows JSON endpoints land in PR5; the existing form-
 * submitting routes (/jobs/{name}/rows/{row_id} POST,
 * /jobs/{name}/train POST, /jobs/{name}/train/stream SSE,
 * /jobs/{name}/download GET) are preserved.
 */
import { z } from "zod";

async function getJson<T extends z.ZodTypeAny>(url: string, schema: T): Promise<z.infer<T>> {
  const r = await fetch(url, { headers: { accept: "application/json" } });
  if (!r.ok) throw new HttpError(r.status, `${r.status} ${r.statusText} ← ${url}`);
  const raw: unknown = await r.json();
  const parsed = schema.safeParse(raw);
  if (!parsed.success) throw new ParseError(url, parsed.error);
  return parsed.data;
}

async function postForm(url: string, body: Record<string, string>): Promise<void> {
  const form = new FormData();
  for (const [k, v] of Object.entries(body)) form.set(k, v);
  const r = await fetch(url, { method: "POST", body: form });
  if (!r.ok) throw new HttpError(r.status, `${r.status} ${r.statusText} ← ${url}`);
}

export const studioApi = {
  jobs: () => getJson("/jobs", z.array(JobSummary)),
  job: (name: string) => getJson(`/jobs/${encodeURIComponent(name)}/rows`, JobDetailResponse),
  rateRow: async (name: string, rowId: string, rating: number | null, rationale: string) => {
    const body: Record<string, string> = { rationale };
    if (rating !== null) body.rating = String(rating);
    await postForm(`/jobs/${encodeURIComponent(name)}/rows/${encodeURIComponent(rowId)}`, body);
  },
  startTraining: (name: string, epochs: number, lr: number) =>
    postForm(`/jobs/${encodeURIComponent(name)}/train`, {
      epochs: String(epochs),
      lr: String(lr),
    }),
  manifest: () => getJson("/api/manifest", Manifest),
} as const;
