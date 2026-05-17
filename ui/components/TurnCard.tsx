"use client";

import { motion } from "framer-motion";
import { AlertCircle, ChevronRight, MessageCircle } from "lucide-react";
import { cn } from "@/lib/cn";
import type { AskResponse } from "@/lib/api";
import { RouteBadge } from "./RouteBadge";
import { CostBadge } from "./CostBadge";
import { AnswerPanel } from "./AnswerPanel";

export interface Turn {
  question: string;
  status: "pending" | "ok" | "error";
  response?: AskResponse;
  error?: string;
}

interface Props {
  turn: Turn;
  index: number;
  isSelected: boolean;
  onSelect: () => void;
}

function totalCost(r: AskResponse): number {
  return (
    (r.synthesis?.cost_usd ?? 0) +
    (r.stats?.cost_usd ?? 0) +
    (r.hybrid?.filter.cost_usd ?? 0)
  );
}

export function TurnCard({ turn, index, isSelected, onSelect }: Props) {
  return (
    <motion.button
      type="button"
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      onClick={onSelect}
      className={cn(
        "group relative block w-full text-left rounded-2xl border bg-surface/70 backdrop-blur-md",
        "transition-all overflow-hidden",
        isSelected
          ? "border-[rgba(255,106,31,0.45)] shadow-[0_0_0_1px_rgba(255,106,31,0.35),0_12px_40px_-12px_rgba(255,106,31,0.35)]"
          : "hairline hover:border-[rgba(255,255,255,0.18)]",
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "absolute left-0 top-0 h-full w-[2px]",
          isSelected
            ? "bg-[linear-gradient(180deg,#ff8a3d,#f15a10_60%,transparent)]"
            : "bg-transparent group-hover:bg-[rgba(255,255,255,0.12)]",
        )}
      />

      <div className="flex items-start gap-3 px-5 pt-4">
        <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-surface-2 text-text-dim">
          <MessageCircle className="h-3.5 w-3.5" />
        </span>
        <p className="flex-1 text-[15px] font-medium leading-6 text-text">
          {turn.question}
        </p>
        <span className="font-mono text-[10px] text-text-dim">#{index + 1}</span>
      </div>

      {turn.status === "pending" && (
        <div className="px-5 py-4">
          <PendingTrace />
        </div>
      )}

      {turn.status === "error" && (
        <div className="m-4 mt-3 flex items-start gap-2 rounded-xl border border-[rgba(251,113,133,0.30)] bg-[rgba(251,113,133,0.08)] px-3 py-2 text-xs text-[#fda4af]">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span className="font-mono">{turn.error}</span>
        </div>
      )}

      {turn.status === "ok" && turn.response && (
        <div className="px-5 pb-4 pt-3 space-y-3">
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
            <span className="ml-auto inline-flex items-center gap-1 text-[11px] text-text-dim">
              View trace
              <ChevronRight
                className={cn(
                  "h-3 w-3 transition-transform",
                  isSelected && "translate-x-0.5",
                )}
                style={isSelected ? { color: "#ffb380" } : undefined}
              />
            </span>
          </div>
          <AnswerPanel
            answer={turn.response.answer}
            citations={turn.response.synthesis?.citations ?? []}
            declined={turn.response.synthesis?.declined}
          />
          {turn.response.not_yet_implemented && (
            <p className="rounded-md border border-[rgba(251,191,36,0.25)] bg-[rgba(251,191,36,0.08)] px-2.5 py-1.5 text-xs text-[#fcd34d]">
              {turn.response.notes || "Route not yet implemented."}
            </p>
          )}
        </div>
      )}
    </motion.button>
  );
}

function PendingTrace() {
  const labels = ["Routing", "Retrieving", "Reading", "Synthesizing"];
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-text-muted">
        <span
          className="inline-block h-2 w-2 animate-pulse rounded-full"
          style={{ background: "#ff6a1f", boxShadow: "0 0 10px #ff6a1f" }}
        />
        Thinking
      </div>
      <div className="flex flex-wrap gap-2">
        {labels.map((l) => (
          <span
            key={l}
            className="shimmer rounded-md border hairline px-2 py-1 text-[11px] text-text-muted"
          >
            {l}…
          </span>
        ))}
      </div>
      <div className="space-y-1.5 pt-1">
        <div className="shimmer h-3 w-11/12 rounded-md" />
        <div className="shimmer h-3 w-9/12 rounded-md" />
        <div className="shimmer h-3 w-10/12 rounded-md" />
      </div>
    </div>
  );
}
