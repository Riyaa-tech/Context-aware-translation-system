// Thin typed client for the FastAPI backend. Every value shown in the UI comes from here.
export class ApiError extends Error {}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { "content-type": "application/json" }, ...init });
  const text = await r.text();
  let body: unknown = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }
  if (!r.ok) {
    const d = (body as { detail?: unknown })?.detail;
    throw new ApiError(typeof d === "string" ? d : Array.isArray(d) ? d.map((x: { msg?: string }) => x.msg).join("; ") : `${r.status} ${r.statusText}`);
  }
  return body as T;
}
export const post = <T,>(path: string, data: unknown) => api<T>(path, { method: "POST", body: JSON.stringify(data) });

export type Decision = "PASS_THROUGH" | "INTERVENE" | "ABSTAIN";
export interface SpanDecision { module: string; item_id: string; span: [number, number]; action: string; reason: string }
export interface PipelineEvent { stage: string; status: string; duration_ms: number; details: Record<string, unknown> }
export interface EnhancedResponse {
  condition: string; source_text: string; translation: string; source_lang: string; target_lang: string; status: string;
  controller_decision: Decision; nllb_input: string; record: Record<string, any>; events: PipelineEvent[];
  model_id: string; model_revision: string | null;
}
export interface BaselineResponse { translation: string; latency_ms: number; status: string; warnings: string[]; model_revision: string | null }
export interface CompareResponse { baseline: BaselineResponse; enhanced: EnhancedResponse; outputs_differ: boolean; enhanced_input_unchanged: boolean }
export interface Direction { source: string; target: string; status: "enabled" | "planned" }
export interface Languages { languages: { code: string; name: string }[]; directions: Direction[] }

/**
 * Settings of the proposed system used by the Translate page. These are the same defaults the old Translate page
 * sent (idiom + selected-context modules, paraphrase mode); they are fixed here instead of shown as controls.
 */
export const PROPOSED_SYSTEM = { modules: ["idiom", "context"], idiom_mode: "paraphrase", context_mode: "selected" } as const;
export const MAX_CONTEXT_SENTENCES = 10; // backend limit (EnhancedRequest.context max_length)

export interface TranslateInput { text: string; source_lang: string; target_lang: string; context: string[] }

/** Split the context box into sentences: one per line, trimmed, blank lines dropped. */
export function contextLines(raw: string): string[] {
  return raw.split("\n").map((s) => s.trim()).filter(Boolean);
}

/** One call to the existing enhanced endpoint (one NLLB call). */
export function translateEnhanced(input: TranslateInput) {
  return post<EnhancedResponse>("/api/translate/enhanced", { ...input, ...PROPOSED_SYSTEM });
}
