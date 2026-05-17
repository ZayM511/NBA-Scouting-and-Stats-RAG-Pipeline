"use client";

import { useEffect, useRef, useState } from "react";
import { postAsk, getHealth, type AskResponse } from "@/lib/api";
import { ChatInput } from "@/components/ChatInput";
import { RouteBadge } from "@/components/RouteBadge";
import { CostBadge } from "@/components/CostBadge";
import { AnswerPanel } from "@/components/AnswerPanel";
import { RetrievalPanel } from "@/components/RetrievalPanel";
import { StatsPanel } from "@/components/StatsPanel";
import { HybridPanel } from "@/components/HybridPanel";

interface Turn {
  question: string;
  status: "pending" | "ok" | "error";
  response?: AskResponse;
  error?: string;
}

export default function Home() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [healthOk, setHealthOk] = useState<boolean | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Ping /health once on mount so the user can see if the API is reachable.
  useEffect(() => {
    getHealth()
      .then((h) => setHealthOk(h.db_ok && h.status === "ok"))
      .catch(() => setHealthOk(false));
  }, []);

  // Auto-scroll to newest turn
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function handleSubmit(question: string) {
    const newTurn: Turn = { question, status: "pending" };
    const idx = turns.length;
    setTurns((t) => [...t, newTurn]);
    setSelected(idx);
    try {
      const response = await postAsk({ question });
      setTurns((t) =>
        t.map((x, i) => (i === idx ? { ...x, status: "ok", response } : x)),
      );
    } catch (err) {
      setTurns((t) =>
        t.map((x, i) =>
          i === idx
            ? { ...x, status: "error", error: err instanceof Error ? err.message : String(err) }
            : x,
        ),
      );
    }
  }

  const pending = turns.some((t) => t.status === "pending");
  const selectedTurn = selected !== null ? turns[selected] : undefined;

  return (
    <div className="flex h-screen flex-col bg-zinc-50 dark:bg-zinc-950">
      <Header healthOk={healthOk} />

      <div className="grid flex-1 grid-cols-1 overflow-hidden md:grid-cols-[1fr_420px]">
        {/* Chat column */}
        <div className="flex flex-col overflow-hidden border-r border-zinc-200 dark:border-zinc-800">
          <div className="flex-1 overflow-y-auto px-4 py-4">
            <div className="mx-auto max-w-2xl space-y-4">
              {turns.length === 0 && <EmptyState />}
              {turns.map((turn, i) => (
                <TurnCard
                  key={i}
                  turn={turn}
                  index={i}
                  isSelected={selected === i}
                  onSelect={() => setSelected(i)}
                />
              ))}
              <div ref={chatEndRef} />
            </div>
          </div>
          <div className="border-t border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900">
            <div className="mx-auto max-w-2xl">
              <ChatInput onSubmit={handleSubmit} disabled={pending} />
            </div>
          </div>
        </div>

        {/* Tool sidebar */}
        <aside className="flex flex-col overflow-hidden bg-white dark:bg-zinc-900">
          <Sidebar turn={selectedTurn} />
        </aside>
      </div>
    </div>
  );
}

function Header({ healthOk }: { healthOk: boolean | null }) {
  return (
    <header className="flex items-center justify-between border-b border-zinc-200 bg-white px-4 py-2.5 dark:border-zinc-800 dark:bg-zinc-900">
      <h1 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
        NBA Scouting + Stats RAG
        <span className="ml-2 text-[11px] font-normal text-zinc-500">2025-26 season</span>
      </h1>
      <div className="flex items-center gap-2 text-xs">
        <span
          className={
            "inline-block h-2 w-2 rounded-full " +
            (healthOk === null
              ? "bg-zinc-400"
              : healthOk
                ? "bg-emerald-500"
                : "bg-red-500")
          }
        />
        <span className="text-zinc-500">
          {healthOk === null ? "checking" : healthOk ? "API ready" : "API down"}
        </span>
      </div>
    </header>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-dashed border-zinc-300 p-6 text-center text-sm text-zinc-500 dark:border-zinc-700">
      <p className="font-medium text-zinc-700 dark:text-zinc-300">Ask a basketball question.</p>
      <p className="mt-1 text-xs">
        Try: <code className="rounded bg-zinc-100 px-1.5 py-0.5 dark:bg-zinc-800">Who leads the league in threes?</code>
      </p>
      <p className="text-xs">
        Or: <code className="rounded bg-zinc-100 px-1.5 py-0.5 dark:bg-zinc-800">How is SGA playing this year?</code>
      </p>
    </div>
  );
}

function TurnCard({
  turn,
  index,
  isSelected,
  onSelect,
}: {
  turn: Turn;
  index: number;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      className={
        "cursor-pointer rounded-lg border bg-white p-3 transition-shadow dark:bg-zinc-900 " +
        (isSelected
          ? "border-zinc-400 shadow-sm dark:border-zinc-500"
          : "border-zinc-200 hover:border-zinc-300 dark:border-zinc-800 dark:hover:border-zinc-700")
      }
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <p className="flex-1 text-sm font-medium text-zinc-900 dark:text-zinc-100">
          {turn.question}
        </p>
        <span className="text-[10px] text-zinc-400">#{index + 1}</span>
      </div>

      {turn.status === "pending" && (
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-zinc-500" />
          Routing & retrieving…
        </div>
      )}

      {turn.status === "error" && (
        <div className="rounded-md bg-red-50 px-2 py-1.5 text-xs text-red-700 dark:bg-red-950 dark:text-red-300">
          {turn.error}
        </div>
      )}

      {turn.status === "ok" && turn.response && (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <RouteBadge
              route={turn.response.route.route}
              reasoning={turn.response.route.reasoning}
            />
            <CostBadge
              costUsd={totalCost(turn.response)}
              elapsedMs={turn.response.elapsed_ms}
              model={turn.response.synthesis?.model}
            />
          </div>
          <AnswerPanel
            answer={turn.response.answer}
            citations={turn.response.synthesis?.citations ?? []}
            declined={turn.response.synthesis?.declined}
          />
          {turn.response.not_yet_implemented && (
            <p className="text-xs text-amber-700 dark:text-amber-300">
              {turn.response.notes || "Route not yet implemented."}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function totalCost(r: AskResponse): number {
  return (
    (r.synthesis?.cost_usd ?? 0) +
    (r.stats?.cost_usd ?? 0) +
    (r.hybrid?.filter.cost_usd ?? 0)
  );
}

function Sidebar({ turn }: { turn?: Turn }) {
  if (!turn) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-center text-xs text-zinc-500">
        Tool calls and retrieval will appear here.
      </div>
    );
  }
  if (turn.status !== "ok" || !turn.response) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-center text-xs text-zinc-500">
        {turn.status === "pending" ? "Running…" : "No data."}
      </div>
    );
  }
  const r = turn.response;
  const cited = r.synthesis?.cited_chunk_ids ?? [];
  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="space-y-4">
        <Section label="Router">
          <p className="text-xs leading-5 text-zinc-700 dark:text-zinc-300">
            {r.route.reasoning}
          </p>
        </Section>

        {r.retrieval && (
          <Section label="Retrieval">
            <RetrievalPanel retrieval={r.retrieval} citedChunkIds={cited} />
          </Section>
        )}

        {r.stats && (
          <Section label="Stats SQL">
            <StatsPanel stats={r.stats} />
          </Section>
        )}

        {r.hybrid && (
          <Section label="Hybrid">
            <HybridPanel hybrid={r.hybrid} citedChunkIds={cited} />
          </Section>
        )}
      </div>
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
        {label}
      </h3>
      {children}
    </section>
  );
}
