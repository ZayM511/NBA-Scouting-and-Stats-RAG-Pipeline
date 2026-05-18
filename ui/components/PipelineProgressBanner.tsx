"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Brain,
  Check,
  Compass,
  Database,
  FileText,
  Layers,
  Loader2,
  MessageCircle,
  Search,
} from "lucide-react";
import type { RouteName } from "@/lib/api";

/**
 * PipelineProgressBanner — visualizes the RAG pipeline for one user turn.
 * Mirrors the architecture diagram:
 *
 *   User Question -> Query Router (Sonnet 4.5)
 *                 -> [Stats Path | Prose Path | Hybrid Path]
 *                 -> Synthesis (Opus 4.6)
 *                 -> Answer + Sources
 *
 * The third stage swaps based on the actual route the question took. While
 * the question is in flight the route is not yet known, so the path tile
 * stays in a neutral "Retrieval" state. Once the response lands, the banner
 * locks to the specific route's tone + sublabel.
 */

type StageTone = { color: string; bg: string; ring: string };

interface Stage {
  id: string;
  label: string;
  sublabel: string;
  Icon: typeof Compass;
  tone: StageTone;
}

const TONE = {
  slate: { color: "#a1a1aa", bg: "rgba(161,161,170,0.14)", ring: "rgba(161,161,170,0.45)" },
  ice: { color: "#7dd3fc", bg: "rgba(125,211,252,0.14)", ring: "rgba(125,211,252,0.48)" },
  violet: { color: "#c4b5fd", bg: "rgba(167,139,250,0.14)", ring: "rgba(167,139,250,0.48)" },
  ember: { color: "#ffb380", bg: "rgba(255,106,31,0.14)", ring: "rgba(255,106,31,0.48)" },
  amber: { color: "#fcd34d", bg: "rgba(251,191,36,0.14)", ring: "rgba(251,191,36,0.50)" },
  emerald: { color: "#6ee7b7", bg: "rgba(110,231,183,0.14)", ring: "rgba(110,231,183,0.50)" },
  rose: { color: "#fda4af", bg: "rgba(251,113,133,0.14)", ring: "rgba(251,113,133,0.48)" },
} as const;

function pathStage(route: RouteName | undefined): Stage {
  switch (route) {
    case "stats":
      return {
        id: "path-stats",
        label: "Stats Path",
        sublabel: "Text-to-SQL → Postgres",
        Icon: Database,
        tone: TONE.ember,
      };
    case "prose":
      return {
        id: "path-prose",
        label: "Prose Path",
        sublabel: "Vector + Cohere Rerank",
        Icon: Search,
        tone: TONE.violet,
      };
    case "hybrid":
      return {
        id: "path-hybrid",
        label: "Hybrid Path",
        sublabel: "SQL filter → Vector",
        Icon: Layers,
        tone: TONE.rose,
      };
    case "oracle":
      return {
        id: "path-oracle",
        label: "Oracle Lore",
        sublabel: "Self-referential",
        Icon: Search,
        tone: TONE.violet,
      };
    default:
      // Route not yet known (still pending). Neutral placeholder.
      return {
        id: "path-pending",
        label: "Retrieval",
        sublabel: "Choosing path…",
        Icon: Search,
        tone: TONE.ember,
      };
  }
}

const SHORT_MODEL: Record<string, string> = {
  "claude-haiku-4-5-20251001": "Haiku 4.5",
  "claude-sonnet-4-5": "Sonnet 4.5",
  "claude-opus-4-6": "Opus 4.6",
  "claude-opus-4-7": "Opus 4.7",
};

function shortenModel(model: string | undefined, fallback: string): string {
  if (!model) return fallback;
  if (SHORT_MODEL[model]) return SHORT_MODEL[model];
  // Strip the "claude-" prefix and a trailing date suffix for unknown IDs.
  return model.replace(/^claude-/, "").replace(/-\d{8}$/, "");
}

interface Props {
  pending: boolean;
  /** ms between stage advances while pending. */
  stepInterval?: number;
  /** "running" animates stages forward; "success" parks every stage at
   *  complete with a green check + emerald glow. */
  phase?: "running" | "success";
  /** Route taken by this question — drives the path tile's label/icon. */
  route?: RouteName;
  /** Synthesis model id from the response, e.g. claude-opus-4-6. */
  synthesisModel?: string;
  /** Router model id. Defaults to Sonnet 4.5 per CLAUDE.md. */
  routerModel?: string;
}

export function PipelineProgressBanner({
  pending,
  stepInterval = 600,
  phase = "running",
  route,
  synthesisModel,
  routerModel,
}: Props) {
  const stages: Stage[] = [
    {
      id: "question",
      label: "User Question",
      sublabel: "Received",
      Icon: MessageCircle,
      tone: TONE.slate,
    },
    {
      id: "router",
      label: "Query Router",
      sublabel: shortenModel(routerModel, "Sonnet 4.5"),
      Icon: Compass,
      tone: TONE.ice,
    },
    pathStage(route),
    {
      id: "synthesis",
      label: "Synthesis",
      sublabel: shortenModel(synthesisModel, "Opus 4.6"),
      Icon: Brain,
      tone: TONE.amber,
    },
    {
      id: "answer",
      label: "Answer + Sources",
      sublabel: phase === "success" ? "Delivered" : "Pending",
      Icon: FileText,
      tone: TONE.emerald,
    },
  ];

  const [activeIdx, setActiveIdx] = useState(0);

  // Advance the active stage while pending. Stop on the last stage so we
  // visually hold there until the response lands.
  useEffect(() => {
    if (!pending || phase === "success") return;
    setActiveIdx(0);
    const id = setInterval(() => {
      setActiveIdx((i) => Math.min(stages.length - 1, i + 1));
    }, stepInterval);
    return () => clearInterval(id);
  }, [pending, stepInterval, phase, stages.length]);

  // Fast-forward to all-complete when the answer is in (or we're explicitly
  // in success phase).
  useEffect(() => {
    if (!pending || phase === "success") setActiveIdx(stages.length);
  }, [pending, phase, stages.length]);

  const success = phase === "success";

  return (
    <motion.div
      data-testid="pipeline-progress"
      data-phase={phase}
      data-route={route ?? "pending"}
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="relative flex w-full flex-col gap-2 rounded-xl border bg-surface/55 px-3 py-2.5 backdrop-blur-xl"
      style={{
        borderColor: success
          ? "rgba(110,231,183,0.40)"
          : "rgba(255,106,31,0.30)",
        background: success
          ? "linear-gradient(90deg, rgba(110,231,183,0.14) 0%, rgba(251,191,36,0.12) 50%, rgba(110,231,183,0.14) 100%)"
          : "linear-gradient(90deg, rgba(125,211,252,0.10) 0%, rgba(255,106,31,0.10) 35%, rgba(167,139,250,0.10) 65%, rgba(251,191,36,0.10) 100%)",
        boxShadow: success
          ? "0 0 0 1px rgba(110,231,183,0.25), 0 14px 32px -16px rgba(110,231,183,0.40)"
          : undefined,
      }}
      role="status"
      aria-live="polite"
      aria-label={success ? "RAG pipeline complete" : "RAG pipeline progress"}
    >
      <div className="flex items-center gap-2">
        <span
          className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.22em]"
          style={{ color: success ? "#6ee7b7" : "#ffb380" }}
          aria-hidden="true"
        >
          {success ? (
            <Check className="h-3 w-3" />
          ) : (
            <Loader2 className="h-3 w-3 animate-spin" />
          )}
          {success ? "Pipeline Complete" : "Live RAG Pipeline"}
        </span>
      </div>

      {/* Stages get their natural width; the row is horizontally scrollable
          when the combined width overflows. Custom scrollbar styling keeps
          the affordance visible after the pipeline lands so users can scroll
          right to see every stage. */}
      <div className="pipeline-stage-row flex items-stretch gap-1.5 overflow-x-auto pb-1">
        {stages.map((stage, i) => {
          const isComplete = success || i < activeIdx;
          const isActive = !success && i === activeIdx && pending;
          return (
            <PipelineStage
              key={stage.id}
              stage={stage}
              isActive={isActive}
              isComplete={isComplete}
              isLast={i === stages.length - 1}
            />
          );
        })}
        <style>{`
          .pipeline-stage-row { scrollbar-width: thin; scrollbar-color: rgba(255,106,31,0.45) transparent; }
          .pipeline-stage-row::-webkit-scrollbar { height: 6px; }
          .pipeline-stage-row::-webkit-scrollbar-track { background: transparent; }
          .pipeline-stage-row::-webkit-scrollbar-thumb { background: rgba(255,106,31,0.45); border-radius: 4px; }
          .pipeline-stage-row::-webkit-scrollbar-thumb:hover { background: rgba(255,106,31,0.65); }
        `}</style>
      </div>
    </motion.div>
  );
}

function PipelineStage({
  stage,
  isActive,
  isComplete,
  isLast,
}: {
  stage: Stage;
  isActive: boolean;
  isComplete: boolean;
  isLast: boolean;
}) {
  const dim = !isActive && !isComplete;
  return (
    <>
      <motion.div
        data-testid={`pipeline-stage-${stage.id}`}
        data-active={isActive}
        data-complete={isComplete}
        layout
        animate={{
          scale: isActive ? 1.03 : 1,
          opacity: dim ? 0.5 : 1,
        }}
        transition={{ duration: 0.25, ease: "easeOut" }}
        className="relative flex w-[220px] shrink-0 items-center gap-2 rounded-lg border bg-surface/65 px-3 py-2 backdrop-blur-md"
        style={{
          borderColor: dim ? "rgba(255,255,255,0.10)" : stage.tone.ring,
          boxShadow: isActive
            ? `0 0 0 1.5px ${stage.tone.ring}, 0 0 18px -4px ${stage.tone.ring}`
            : isComplete
              ? `inset 0 0 0 1px ${stage.tone.ring}`
              : "inset 0 0 0 1px rgba(255,255,255,0.06)",
        }}
      >
        <span
          className="relative inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full"
          style={{ background: dim ? "rgba(255,255,255,0.04)" : stage.tone.bg }}
        >
          {isComplete ? (
            <Check
              className="h-3.5 w-3.5"
              style={{ color: stage.tone.color }}
              aria-hidden="true"
            />
          ) : (
            <stage.Icon
              className={`h-3.5 w-3.5 ${isActive ? "pipeline-stage-active-icon" : ""}`}
              style={{ color: dim ? "#71717a" : stage.tone.color }}
              aria-hidden="true"
            />
          )}
          {isActive && (
            <span
              aria-hidden="true"
              className="absolute inset-0 animate-ping rounded-full"
              style={{ background: stage.tone.ring, opacity: 0.45 }}
            />
          )}
        </span>
        <span className="flex min-w-0 flex-col leading-tight">
          <span
            className="truncate text-[10.5px] font-semibold uppercase tracking-[0.10em]"
            style={{ color: dim ? "#a1a1aa" : stage.tone.color }}
          >
            {stage.label}
          </span>
          <span
            className="truncate text-[9.5px] uppercase tracking-[0.10em]"
            style={{ color: dim ? "#52525b" : "rgba(228,228,231,0.62)" }}
          >
            {stage.sublabel}
          </span>
        </span>
      </motion.div>
      {!isLast && (
        <span
          aria-hidden="true"
          className="relative my-auto h-[2px] w-2.5 shrink-0 overflow-hidden rounded-full bg-white/8"
        >
          <motion.span
            className="absolute inset-y-0 left-0 bg-[linear-gradient(90deg,transparent,#ff8a3d,transparent)]"
            initial={{ x: "-100%", opacity: 0 }}
            animate={
              isComplete
                ? { x: "100%", opacity: 0.9 }
                : isActive
                  ? { x: ["-100%", "100%"], opacity: [0.4, 0.9, 0.4] }
                  : { x: "-100%", opacity: 0 }
            }
            transition={
              isActive
                ? { duration: 1.1, repeat: Infinity, ease: "easeInOut" }
                : { duration: 0.35, ease: "easeOut" }
            }
            style={{ width: "60%" }}
          />
          {isComplete && (
            <span
              aria-hidden="true"
              className="absolute inset-y-0 left-0 right-0"
              style={{
                background: `linear-gradient(90deg, ${stage.tone.ring}, transparent)`,
                opacity: 0.7,
              }}
            />
          )}
        </span>
      )}

      <style>{`
        @media (prefers-reduced-motion: reduce) {
          .pipeline-stage-active-icon { animation: none; }
        }
      `}</style>
    </>
  );
}
