"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, ChevronRight, MessageCircle } from "lucide-react";
import { cn } from "@/lib/cn";
import type { AskResponse } from "@/lib/api";
import { RouteBadge } from "./RouteBadge";
import { CostBadge } from "./CostBadge";
import { AnswerPanel } from "./AnswerPanel";
import { PipelineProgressBanner } from "./PipelineProgressBanner";

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
  // Phase machine for the pending → success → answer transition. We hold a
  // "success" phase for ~900 ms when the response lands so the user sees
  // every pipeline stage check off before the answer panel takes the slot.
  const [phase, setPhase] = useState<"idle" | "running" | "success">(
    turn.status === "pending" ? "running" : "idle",
  );
  const prevStatus = useRef(turn.status);
  useEffect(() => {
    const was = prevStatus.current;
    prevStatus.current = turn.status;
    if (turn.status === "pending") {
      setPhase("running");
      return;
    }
    if (was === "pending" && turn.status === "ok") {
      setPhase("success");
      const t = setTimeout(() => setPhase("idle"), 900);
      return () => clearTimeout(t);
    }
    // Error or any other status flips us back to idle so the error pill renders.
    if (turn.status !== "ok") setPhase("idle");
  }, [turn.status]);

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

      <AnimatePresence mode="wait" initial={false}>
        {phase === "running" && (
          <motion.div
            key="banner-running"
            initial={{ opacity: 0, y: -2 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="px-5 pt-3 pb-4"
          >
            <div className="h-14 w-full">
              <PipelineProgressBanner pending phase="running" />
            </div>
          </motion.div>
        )}
        {phase === "success" && (
          <motion.div
            key="banner-success"
            initial={{ opacity: 0, scale: 0.99 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.99 }}
            transition={{ duration: 0.28, ease: "easeOut" }}
            className="px-5 pt-3 pb-4"
          >
            <div className="h-14 w-full">
              <PipelineProgressBanner pending={false} phase="success" />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {turn.status === "error" && <TurnError error={turn.error ?? ""} />}

      {turn.status === "ok" && phase === "idle" && turn.response && (
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

/**
 * TurnError — error pill with a friendlier presentation. Detects credential
 * failures from the wording the api.ts wrapper produces and shows a short
 * "Edit .env" hint. Falls back to a plain monospace dump for anything that
 * looks like a stack trace or a raw payload.
 */
function TurnError({ error }: { error: string }) {
  const isCredentialError =
    /api key|x-api-key|ANTHROPIC_API_KEY|llm provider rejected/i.test(error);
  const looksTechnical = /\{|\[|stack|traceback|\bat \s/i.test(error);
  return (
    <div
      data-testid="turn-error"
      className="m-4 mt-3 flex items-start gap-2 rounded-xl border border-[rgba(251,113,133,0.30)] bg-[rgba(251,113,133,0.08)] px-3 py-2.5 text-[12.5px] leading-5 text-[#fda4af]"
    >
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1 space-y-1.5">
        <p className={looksTechnical && !isCredentialError ? "font-mono text-[11px]" : ""}>
          {error}
        </p>
        {isCredentialError && (
          <p className="text-[11px] text-[#fda4af]/80">
            Fix: open <span className="font-mono text-[#ffd0c0]">.env</span> in the
            project root, replace{" "}
            <span className="font-mono text-[#ffd0c0]">ANTHROPIC_API_KEY</span>{" "}
            with a current key from{" "}
            <a
              href="https://console.anthropic.com/settings/keys"
              target="_blank"
              rel="noreferrer"
              className="underline decoration-dotted underline-offset-2 hover:text-[#ffd0c0]"
            >
              console.anthropic.com/settings/keys
            </a>
            , then restart the FastAPI server.
          </p>
        )}
      </div>
    </div>
  );
}


