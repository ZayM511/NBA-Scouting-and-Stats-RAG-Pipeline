"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Sparkles, X } from "lucide-react";
import { cn } from "@/lib/cn";

/**
 * AboutTheOracle — small interactive disclosure that lives under the
 * basketball orb.
 *
 *   Closed state: a compact pill that says "About The Oracle" with an
 *   attention-grabbing pulse / shimmer animation. Hovering brightens it.
 *
 *   Open state: a slightly taller card that types each statement
 *   letter-by-letter, one statement at a time. When the last statement
 *   finishes, the ember cursor rests with a soft pulse on the final line.
 *
 *   The user can close the card by clicking the same button (it doubles as
 *   the title bar) or pressing Escape while the card is focused. Reopen
 *   restarts the typing from the first statement.
 */

export const ABOUT_LINES: string[] = [
  "I am the Ball Knowledge Oracle.",
  "I know ball because I am one… Which means I know more ball than you.",
  "Every box score, every scout's whisper, every beat-writer column of the 2025–26 NBA season — I've read it.",
  "Under the hood I'm a Sonnet-routed RAG pipeline: SQL on the numbers, vector search on the prose, citations on everything.",
  "I don't pick teams. I don't have favorites. I only have sources.",
  "If the truth bruises your fandom, that is a fandom problem — not an Oracle problem.",
  "Ask. Rebut. Ask again. I keep the receipts.",
];

/** Per-line className override applied on top of the base statement style.
 *  Line 0 gets bold ember; everything else inherits the default look. */
const LINE_STYLES: Record<number, string> = {
  0: "text-[#ffb380] font-bold",
};

interface Props {
  lines?: string[];
  /** Per-character delay while typing, in ms. */
  charDelay?: number;
  /** Pause after one statement finishes before the next begins. */
  linePause?: number;
  /** Restart token — bump this from the parent to reset the panel. */
  runKey?: number | string;
  className?: string;
}

export function AboutTheOracle({
  lines = ABOUT_LINES,
  charDelay = 22,
  linePause = 380,
  runKey = 0,
  className,
}: Props) {
  const [open, setOpen] = useState(false);
  const [lineIdx, setLineIdx] = useState(0);
  const [charCount, setCharCount] = useState(0);
  const [skipped, setSkipped] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // External reset (parent's runKey changes).
  useEffect(() => {
    setOpen(false);
    setLineIdx(0);
    setCharCount(0);
    setSkipped(false);
    if (timer.current) clearTimeout(timer.current);
  }, [runKey]);

  // Drive the typewriter while the card is open.
  useEffect(() => {
    if (!open || skipped) return;
    if (lineIdx >= lines.length) return;
    const current = lines[lineIdx];
    if (charCount < current.length) {
      timer.current = setTimeout(
        () => setCharCount((c) => c + 1),
        charDelay,
      );
    } else if (lineIdx < lines.length - 1) {
      timer.current = setTimeout(() => {
        setLineIdx((i) => i + 1);
        setCharCount(0);
      }, linePause);
    }
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [open, lineIdx, charCount, lines, charDelay, linePause, skipped]);

  function toggleOpen() {
    setOpen((prev) => {
      const next = !prev;
      if (next) {
        // Restart typing each time the card opens.
        setLineIdx(0);
        setCharCount(0);
        setSkipped(false);
      } else {
        if (timer.current) clearTimeout(timer.current);
      }
      return next;
    });
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape" && open) {
      e.preventDefault();
      setOpen(false);
    }
  }

  function handleSkip(e: React.MouseEvent) {
    e.stopPropagation();
    if (timer.current) clearTimeout(timer.current);
    setSkipped(true);
    setLineIdx(lines.length - 1);
    setCharCount(lines[lines.length - 1].length);
  }

  const done = skipped || (lineIdx === lines.length - 1 && charCount >= lines[lineIdx].length);

  // Lines that have already completed render whole; the active line renders
  // up to `charCount`.
  const renderedLines = useMemo(() => {
    if (skipped) return lines.map((l, i) => ({ text: l, isActive: i === lines.length - 1, complete: true }));
    return lines.slice(0, lineIdx + 1).map((l, i) => ({
      text: i < lineIdx ? l : l.slice(0, charCount),
      isActive: i === lineIdx,
      complete: i < lineIdx,
    }));
  }, [lines, lineIdx, charCount, skipped]);

  return (
    <div
      data-testid="about-the-oracle"
      data-open={open}
      onKeyDown={onKeyDown}
      className={cn("relative w-full max-w-[640px]", className)}
    >
      {/* Closed-state attention ring (only visible when closed). */}
      <AnimatePresence>
        {!open && (
          <motion.span
            key="ring"
            aria-hidden="true"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="pointer-events-none absolute -inset-1 rounded-full"
            style={{
              background:
                "radial-gradient(circle at 50% 50%, rgba(255,106,31,0.25) 0%, transparent 65%)",
              filter: "blur(8px)",
            }}
          />
        )}
      </AnimatePresence>

      <motion.button
        type="button"
        data-testid="about-the-oracle-trigger"
        onClick={toggleOpen}
        aria-expanded={open}
        aria-controls="about-the-oracle-content"
        whileHover={{ y: -1 }}
        whileTap={{ scale: 0.98 }}
        className={cn(
          "group relative z-10 inline-flex w-auto items-center gap-2 rounded-full border bg-surface/80 px-4 py-2 backdrop-blur-xl transition-colors",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(255,106,31,0.55)]",
          open
            ? "border-[rgba(255,106,31,0.55)] text-text"
            : "hairline-strong text-text-muted hover:border-[rgba(255,106,31,0.45)] hover:text-text",
        )}
      >
        {/* Shimmer sweep on the closed state — pure CSS, very cheap. */}
        {!open && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 overflow-hidden rounded-full"
          >
            <span className="about-shimmer absolute inset-y-0 -left-1/3 w-1/3" />
          </span>
        )}

        <motion.span
          animate={
            !open
              ? {
                  scale: [1, 1.18, 1],
                  filter: [
                    "drop-shadow(0 0 0px rgba(255,106,31,0))",
                    "drop-shadow(0 0 8px rgba(255,106,31,0.7))",
                    "drop-shadow(0 0 0px rgba(255,106,31,0))",
                  ],
                }
              : { scale: 1, filter: "drop-shadow(0 0 0px rgba(255,106,31,0))" }
          }
          transition={
            !open
              ? { duration: 2.4, repeat: Infinity, ease: "easeInOut" }
              : { duration: 0.2 }
          }
          className="relative inline-flex h-5 w-5 items-center justify-center"
        >
          <Sparkles className="h-3.5 w-3.5 text-[#ffb380]" />
        </motion.span>
        <span className="text-[12.5px] font-semibold uppercase tracking-[0.22em]">
          About The Oracle
        </span>
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 text-text-dim transition-transform duration-300",
            open ? "rotate-180 text-[#ffb380]" : "",
          )}
        />
      </motion.button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="content"
            id="about-the-oracle-content"
            data-testid="about-the-oracle-content"
            initial={{ height: 0, opacity: 0, y: -4 }}
            animate={{ height: "auto", opacity: 1, y: 0 }}
            exit={{ height: 0, opacity: 0, y: -4 }}
            transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
            className="relative z-10 mt-3 overflow-hidden rounded-2xl border hairline-strong bg-surface/80 backdrop-blur-xl"
          >
            <div className="relative px-5 pb-4 pt-3">
              {/* Header row inside the panel: Transmission tag + the
                  Skip / Close controls. Living *inside* the panel padding
                  means the outer overflow-hidden (required for the
                  height animation) doesn't clip them at the top edge. */}
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-md border hairline-strong bg-bg/85 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-text-muted">
                  <span
                    className="h-1 w-1 rounded-full"
                    style={{ background: "#ff6a1f", boxShadow: "0 0 8px #ff6a1f" }}
                  />
                  Transmission · live
                </span>
                <div className="flex items-center gap-1.5">
                  {!done && (
                    <button
                      type="button"
                      data-testid="about-skip"
                      onClick={handleSkip}
                      className="rounded-md border hairline bg-surface/70 px-2 py-1 text-[10px] uppercase tracking-wider text-text-dim transition-colors hover:border-[rgba(255,106,31,0.4)] hover:text-[#ffb380]"
                    >
                      Skip
                    </button>
                  )}
                  <button
                    type="button"
                    data-testid="about-close"
                    onClick={() => setOpen(false)}
                    aria-label="Close About panel"
                    title="Close (Esc)"
                    className="inline-flex h-7 w-7 items-center justify-center rounded-md border hairline bg-surface/70 text-text-dim transition-colors hover:border-[rgba(255,106,31,0.4)] hover:text-[#ffb380]"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              {/* Scrollable statements. Capped at 12vh so panel + both
                  rows of suggestion chips fit between the title and the
                  chat input on a 900-tall viewport. Wheel scrolls past
                  whatever statement is mid-type so the user can read
                  fully-typed lines. */}
              <div
                data-testid="about-statements"
                className="mt-2 max-h-[12vh] space-y-1.5 overflow-y-auto overscroll-contain pr-2 text-left"
                style={{ scrollbarGutter: "stable" }}
                onWheel={(e) => e.stopPropagation()}
              >
                {renderedLines.map((entry, i) => {
                  const isFinal = i === lines.length - 1;
                  const lineStyle = LINE_STYLES[i] ?? "";
                  return (
                    <motion.p
                      key={i}
                      layout
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.25, ease: "easeOut" }}
                      data-line-index={i}
                      className={cn(
                        "text-pretty text-[13.5px] md:text-[14.5px] leading-[1.6]",
                        // The per-line override wins if set; otherwise fall
                        // through to active vs. completed muted styling.
                        lineStyle ||
                          (entry.isActive && !entry.complete
                            ? "text-text"
                            : "text-text-muted"),
                      )}
                    >
                      {entry.text}
                      {(entry.isActive || (isFinal && done)) && (
                        <Cursor pulse={isFinal && done} />
                      )}
                    </motion.p>
                  );
                })}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <style>{`
        @keyframes about-shimmer-keyframes {
          0%   { transform: translateX(-100%); opacity: 0; }
          40%  { opacity: 1; }
          100% { transform: translateX(550%); opacity: 0; }
        }
        .about-shimmer {
          background: linear-gradient(110deg,
            transparent 0%,
            rgba(255,255,255,0.10) 35%,
            rgba(255,166,90,0.35) 50%,
            rgba(255,255,255,0.10) 65%,
            transparent 100%);
          animation: about-shimmer-keyframes 3.4s ease-in-out infinite;
        }
        @media (prefers-reduced-motion: reduce) {
          .about-shimmer { animation: none; opacity: 0; }
        }
      `}</style>
    </div>
  );
}

function Cursor({ pulse }: { pulse: boolean }) {
  return (
    <motion.span
      aria-hidden="true"
      initial={{ opacity: 1 }}
      animate={{ opacity: pulse ? [1, 0.18, 1] : [1, 0, 1] }}
      transition={{
        duration: pulse ? 1.4 : 0.85,
        repeat: Infinity,
        ease: "easeInOut",
      }}
      className="ml-[3px] inline-block h-[1em] w-[2px] translate-y-[3px] rounded-sm align-middle"
      style={{
        background: "#ff6a1f",
        boxShadow: "0 0 8px rgba(255,106,31,0.65)",
      }}
    />
  );
}
