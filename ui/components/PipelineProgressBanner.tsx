"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Brain,
  Check,
  Compass,
  Loader2,
  Search,
  SlidersHorizontal,
} from "lucide-react";

/**
 * PipelineProgressBanner — sits in the header's state-banner slot while a
 * question is in flight. Shows the four RAG pipeline stages animating in
 * sequence:
 *
 *   [Router] -> [Retrieval] -> [Rerank] -> [Synthesis]
 *
 * Drives entirely off the parent's `pending` prop. While pending is true,
 * the active stage advances every ~700 ms and pauses on the final stage.
 * When pending flips false (the answer arrives), every stage is marked
 * complete so the user sees the full chain finish before the banner
 * returns to its normal state.
 *
 * Stages are styled like the existing TickerCards for family resemblance,
 * connected by a thin shimmer line that lights up after each stage
 * completes. Honors `prefers-reduced-motion`.
 */

type StageId = "router" | "retrieval" | "rerank" | "synthesis";

interface Stage {
  id: StageId;
  label: string;
  Icon: typeof Compass;
  tone: { color: string; bg: string; ring: string };
}

const STAGES: Stage[] = [
  {
    id: "router",
    label: "Router",
    Icon: Compass,
    tone: { color: "#7dd3fc", bg: "rgba(125,211,252,0.14)", ring: "rgba(125,211,252,0.48)" },
  },
  {
    id: "retrieval",
    label: "Retrieval",
    Icon: Search,
    tone: { color: "#ffb380", bg: "rgba(255,106,31,0.14)", ring: "rgba(255,106,31,0.48)" },
  },
  {
    id: "rerank",
    label: "Rerank",
    Icon: SlidersHorizontal,
    tone: { color: "#c4b5fd", bg: "rgba(167,139,250,0.14)", ring: "rgba(167,139,250,0.48)" },
  },
  {
    id: "synthesis",
    label: "Synthesis",
    Icon: Brain,
    tone: { color: "#fcd34d", bg: "rgba(251,191,36,0.14)", ring: "rgba(251,191,36,0.50)" },
  },
];

interface Props {
  pending: boolean;
  /** ms between stage advances while pending. */
  stepInterval?: number;
  /** "running" (default) animates stages forward while pending.
   *  "success" parks every stage at complete and renders a one-shot
   *  green checkmark burst, used by the parent right before unmount. */
  phase?: "running" | "success";
}

export function PipelineProgressBanner({
  pending,
  stepInterval = 700,
  phase = "running",
}: Props) {
  const [activeIdx, setActiveIdx] = useState(0);

  // Advance the active stage while we're pending. Stop on the last stage
  // and wait for the answer to arrive.
  useEffect(() => {
    if (!pending || phase === "success") return;
    setActiveIdx(0);
    const id = setInterval(() => {
      setActiveIdx((i) => Math.min(STAGES.length - 1, i + 1));
    }, stepInterval);
    return () => clearInterval(id);
  }, [pending, stepInterval, phase]);

  // When pending flips false (or we're explicitly in success phase),
  // fast-forward to "all complete" by parking activeIdx past the last
  // stage so every card renders its checkmark.
  useEffect(() => {
    if (!pending || phase === "success") setActiveIdx(STAGES.length);
  }, [pending, phase]);

  const success = phase === "success";

  return (
    <motion.div
      data-testid="pipeline-progress"
      data-phase={phase}
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.25 }}
      className="relative flex h-full w-full items-center justify-start gap-1.5 rounded-xl border bg-surface/55 px-3 backdrop-blur-xl"
      style={{
        borderColor: success
          ? "rgba(110,231,183,0.45)"
          : "rgba(255,106,31,0.30)",
        background: success
          ? "linear-gradient(90deg, rgba(110,231,183,0.18) 0%, rgba(251,191,36,0.16) 50%, rgba(110,231,183,0.18) 100%)"
          : "linear-gradient(90deg, rgba(125,211,252,0.10) 0%, rgba(255,106,31,0.10) 35%, rgba(167,139,250,0.10) 65%, rgba(251,191,36,0.12) 100%)",
        boxShadow: success
          ? "0 0 0 1px rgba(110,231,183,0.30), 0 14px 32px -16px rgba(110,231,183,0.45)"
          : undefined,
      }}
      role="status"
      aria-live="polite"
      aria-label={success ? "RAG pipeline complete" : "RAG pipeline progress"}
    >
      <span
        className="mr-1 inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.20em]"
        style={{ color: success ? "#6ee7b7" : "#ffb380" }}
        aria-hidden="true"
      >
        {success ? (
          <Check className="h-3.5 w-3.5" />
        ) : (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        )}
        {success ? "Synthesis Complete" : "Live RAG"}
      </span>
      {STAGES.map((stage, i) => {
        const isComplete = success || i < activeIdx;
        const isActive = !success && i === activeIdx && pending;
        return (
          <PipelineStage
            key={stage.id}
            stage={stage}
            isActive={isActive}
            isComplete={isComplete}
            isLast={i === STAGES.length - 1}
          />
        );
      })}
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
          scale: isActive ? 1.04 : 1,
          opacity: dim ? 0.45 : 1,
        }}
        transition={{ duration: 0.25, ease: "easeOut" }}
        className="relative flex shrink-0 items-center gap-1.5 rounded-full border bg-surface/65 px-2.5 py-1 backdrop-blur-md"
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
          className="relative inline-flex h-5 w-5 items-center justify-center rounded-full"
          style={{ background: dim ? "rgba(255,255,255,0.04)" : stage.tone.bg }}
        >
          {isComplete ? (
            <Check
              className="h-3 w-3"
              style={{ color: stage.tone.color }}
              aria-hidden="true"
            />
          ) : (
            <stage.Icon
              className={`h-3 w-3 ${isActive ? "pipeline-stage-active-icon" : ""}`}
              style={{ color: dim ? "#71717a" : stage.tone.color }}
              aria-hidden="true"
            />
          )}
          {isActive && (
            <span
              aria-hidden="true"
              className="absolute inset-0 animate-ping rounded-full"
              style={{ background: stage.tone.ring, opacity: 0.5 }}
            />
          )}
        </span>
        <span
          className="text-[11px] font-semibold uppercase tracking-[0.16em] whitespace-nowrap"
          style={{ color: dim ? "#a1a1aa" : stage.tone.color }}
        >
          {stage.label}
        </span>
      </motion.div>
      {!isLast && (
        <span
          aria-hidden="true"
          className="relative h-[2px] w-4 shrink-0 overflow-hidden rounded-full bg-white/8"
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
