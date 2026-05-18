// Typed client for the FastAPI /ask endpoint. Shapes mirror src/api/server.py
// AskResponse exactly.

// The first three correspond to API routes; "oracle" is a frontend-only
// route used when oracleLore.ts intercepts a self-referential question and
// short-circuits the pipeline.
export type RouteName = "stats" | "prose" | "hybrid" | "oracle";

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

/** Friendly /ask wrapper. Translates upstream-credential failures into a
 *  one-sentence error the TurnCard can show without exposing raw provider
 *  JSON to the user. */
export async function postAsk(body: AskRequest): Promise<AskResponse> {
  const res = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.ok) return (await res.json()) as AskResponse;

  // Try to parse the body as JSON first; fall back to text. FastAPI's
  // HTTPException(detail={...}) returns {"detail": {...}}; HTTPException
  // with a string detail returns {"detail": "..."}.
  let bodyText = "";
  let parsed: unknown = null;
  try {
    bodyText = await res.text();
    parsed = JSON.parse(bodyText);
  } catch {
    // bodyText keeps the raw payload if it wasn't JSON.
  }
  const detail = (parsed as { detail?: unknown } | null)?.detail;

  // 1. Backend already translated to llm_unauthenticated — use its message.
  if (
    detail &&
    typeof detail === "object" &&
    (detail as { code?: string }).code === "llm_unauthenticated"
  ) {
    throw new Error(
      (detail as { message?: string }).message ??
        "The Oracle's API key needs attention.",
    );
  }

  // 2. Raw Anthropic / Voyage / Cohere auth payload leaked through.
  const haystack =
    typeof detail === "string"
      ? detail
      : detail !== undefined
        ? JSON.stringify(detail)
        : bodyText;
  if (/invalid x-api-key|authentication_error|"errorCode"\s*:\s*401/i.test(haystack)) {
    throw new Error(
      "The Oracle's LLM provider rejected its API key. Update ANTHROPIC_API_KEY in .env and restart the backend.",
    );
  }

  // 3. Everything else — surface a trimmed raw detail so debugging is still
  //    possible without a 4-screen wall of JSON.
  const trimmed = haystack.slice(0, 280);
  throw new Error(`POST /ask failed (${res.status}): ${trimmed}`);
}

export async function getHealth(): Promise<{ status: string; db_ok: boolean; note: string }> {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) throw new Error(`GET /health ${res.status}`);
  return (await res.json()) as { status: string; db_ok: boolean; note: string };
}

// ---- Header endpoint ------------------------------------------------------

export type HeaderMode = "season" | "upcoming" | "live" | "recap";

export interface TeamMeta {
  abbr: string;
  city: string;
  name: string;
  conference: "East" | "West";
  primary: string;
  secondary: string;
  arena: string;
  arena_timezone: string;
}

export interface TeamLite {
  abbr: string;
  city: string;
  name: string;
  primary: string;
  secondary: string;
  conference: string;
  record: string | null;
}

export type HeadlineCategory =
  | "leaders"
  | "scores"
  | "upcoming"
  | "awards"
  | "facts"
  | "divider";

export interface Headline {
  kind: "player" | "team" | "team-leader" | "note" | "divider";
  label: string;
  primary: string;
  secondary: string;
  metric: string;
  tone: "ember" | "ice" | "emerald" | "violet" | "rose" | "amber";
  team_abbr: string | null;
  category?: HeadlineCategory | null;
}

export interface GameLeader {
  name: string;
  team_abbr: string;
  line: string;
}

export interface RecentGame {
  label: string;
  date: string;
  home: TeamLite;
  away: TeamLite;
  home_score: number;
  away_score: number;
  leaders: GameLeader[];
  note: string | null;
}

export interface UpcomingGame {
  label: string;
  tipoff_utc: string;
  arena: string;
  arena_city: string;
  arena_timezone: string;
  home: TeamLite;
  away: TeamLite;
  series_state: string | null;
  note: string | null;
}

export interface LiveGame {
  label: string;
  quarter: number;
  clock: string;
  home: TeamLite;
  away: TeamLite;
  home_score: number;
  away_score: number;
  leaders: GameLeader[];
  highlight: string | null;
}

export interface HeaderPayload {
  generated_at: string;
  mode: HeaderMode;
  headlines: Headline[];
  recent: RecentGame | null;
  upcoming: UpcomingGame | null;
  live: LiveGame | null;
  team_directory: Record<string, TeamMeta>;
}

export type TickerScope = "playoffs" | "regular";

export async function getHeader(
  mode: "auto" | HeaderMode = "auto",
  scope: TickerScope = "playoffs",
): Promise<HeaderPayload> {
  const res = await fetch(`${API_URL}/api/header?mode=${mode}&scope=${scope}`);
  if (!res.ok) throw new Error(`GET /api/header ${res.status}`);
  return (await res.json()) as HeaderPayload;
}
