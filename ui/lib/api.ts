// Typed client for the FastAPI /ask endpoint. Shapes mirror src/api/server.py
// AskResponse exactly.

export type RouteName = "stats" | "prose" | "hybrid";

export interface RouteOut {
  route: RouteName;
  reasoning: string;
}

export interface CitationOut {
  citation_index: number;
  chunk_id: number;
}

export interface SynthesisOut {
  answer: string;
  citations: CitationOut[];
  cited_chunk_ids: number[];
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  declined: boolean;
}

export interface ChunkOut {
  chunk_id: number;
  text: string;
  source: string;
  article_type: string;
  date: string | null;
  score: number;
  player_ids: number[];
}

export interface RetrievalOut {
  bm25_count: number;
  dense_count: number;
  merged_count: number;
  chunks: ChunkOut[];
}

export interface StatsOut {
  status: string;
  sql: string | null;
  params: Record<string, unknown> | null;
  explanation: string | null;
  rows: Record<string, unknown>[] | null;
  row_count: number | null;
  elapsed_ms: number | null;
  cost_usd: number;
  error: string | null;
}

export interface HybridFilterOut {
  sql: string;
  params: Record<string, unknown>;
  explanation: string;
  player_ids: number[];
  cost_usd: number;
  status: string;
  // Phase L.4: numeric rows the synthesis layer used alongside the chunks.
  rows: Record<string, unknown>[];
  column_names: string[];
  row_count: number;
}

export interface HybridOut {
  status: string;
  filter: HybridFilterOut;
  retrieval: RetrievalOut | null;
  notes: string;
}

export interface AskResponse {
  question: string;
  route: RouteOut;
  answer: string;
  synthesis: SynthesisOut | null;
  retrieval: RetrievalOut | null;
  stats: StatsOut | null;
  hybrid: HybridOut | null;
  not_yet_implemented: boolean;
  notes: string;
  elapsed_ms: number;
}

export interface AskRequest {
  question: string;
  top_k?: number;
  player_ids?: number[] | null;
  source?: string | null;
}

// API_URL defaults to the local FastAPI dev server. Override at build time with
// NEXT_PUBLIC_API_URL for a different host (e.g. deploy).
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function postAsk(body: AskRequest): Promise<AskResponse> {
  const res = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`POST /ask failed (${res.status}): ${detail.slice(0, 500)}`);
  }
  return (await res.json()) as AskResponse;
}

export async function getHealth(): Promise<{ status: string; db_ok: boolean; note: string }> {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) throw new Error(`GET /health ${res.status}`);
  return (await res.json()) as { status: string; db_ok: boolean; note: string };
}
