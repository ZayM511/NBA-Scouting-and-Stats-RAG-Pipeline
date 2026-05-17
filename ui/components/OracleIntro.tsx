"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { SkipForward } from "lucide-react";
import { cn } from "@/lib/cn";

/**
 * OracleIntro — the Ball Knowledge Oracle's opening monologue.
 *
 * Each statement appears one after the other, word-by-word, with each word
 * fading + sliding into place on a tight stagger. Completed statements stay
 * visible at slightly reduced emphasis; the active line carries a blinking
 * ember cursor; when all statements are revealed the cursor pulses softly
 * on the final line.
 *
 * A "skip" affordance lets repeat visitors blow past the reveal. The
 * animation re-runs whenever `runKey` changes — used by the page to
 * retrigger the intro when the user clicks "New chat" to come home.
 */

export const ORACLE_INTRO_LINES: string[] = [
  "I am the Ball Knowledge Oracle.",
  "Every box score, every scout's whisper, every beat-writer column of the 2025–26 NBA season — I've read it.",
  "Under the hood I'm a Sonnet-routed RAG pipeline: SQL on the numbers, vector search on the prose, citations on everything.",
  "I don't pick teams. I don't have favorites. I only have sources.",
  "If the truth bruises your fandom, that is a fandom problem — not an Oracle problem.",
  "Ask. Rebut. Ask again. I keep the receipts.",
];

interface Props {
  lines?: string[];
  /** Stagger between words within a statement (seconds). */
  wordStagger?: number;
  /** Pause after a statement finishes before the next begins (ms). */
  linePause?: number;
  /** Bump this to restart the animation from scratch. */
  runKey?: number | string;
  className?: string;
}

export function OracleIntro({
  lines = ORACLE_INTRO_LINES,
  wordStagger = 0.045,
  linePause = 380,
  runKey = 0,
  className,
}: Props) {
  const [revealedLineIdx, setRevealedLineIdx] = useState(0);
  const [skipped, setSkipped] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Pre-tokenize each line into words. Memoized so identical line arrays
  // don't re-split on every render.
  const tokenizedLines = useMemo(
    () => lines.map((line) => line.split(/(\s+)/)),
    [lines],
  );

  // Reset whenever the runKey changes.
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    setRevealedLineIdx(0);
    setSkipped(false);
  }, [runKey]);

  // Advance to the next line once the current one's words have all rendered.
  useEffect(() => {
    if (skipped) return;
    if (revealedLineIdx >= lines.length - 1) return;

    const currentWords = tokenizedLines[revealedLineIdx].filter(
      (t) => !/^\s+$/.test(t),
    ).length;
    const revealDurationMs =
      currentWords * wordStagger * 1000 + 300; // 300ms for the last word to settle
    const totalDelay = revealDurationMs + linePause;

    timer.current = setTimeout(() => {
      setRevealedLineIdx((i) => Math.min(i + 1, lines.length - 1));
    }, totalDelay);

    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [revealedLineIdx, lines.length, tokenizedLines, wordStagger, linePause, skipped]);

  const done = skipped || revealedLineIdx >= lines.length - 1;
  const visibleCount = skipped ? lines.length : revealedLineIdx + 1;

  function handleSkip() {
    if (timer.current) clearTimeout(timer.current);
    setSkipped(true);
    setRevealedLineIdx(lines.length - 1);
  }

  return (
    <div className={cn("relative w-full", className)}>
      <div className="space-y-1.5 text-left">
        <AnimatePresence initial={false}>
          {Array.from({ length: visibleCount }).map((_, i) => {
            const tokens = tokenizedLines[i];
            const isActive = !skipped && i === revealedLineIdx;
            const isFinal = i === lines.length - 1;
            // If skipped, all lines instant; otherwise the active line uses
            // word-stagger and the previously-done lines render whole.
            const stagger = skipped ? 0 : isActive ? wordStagger : 0;
            return (
              <motion.p
                key={i}
                layout
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.28, ease: "easeOut" }}
                className={cn(
                  "text-pretty text-[13.5px] md:text-[14.5px] leading-[1.6]",
                  isActive ? "text-text" : "text-text-muted",
                )}
              >
                <motion.span
                  initial="hidden"
                  animate="show"
                  variants={{
                    hidden: {},
                    show: { transition: { staggerChildren: stagger } },
                  }}
                  className="inline"
                >
                  {tokens.map((tok, ti) => {
                    if (/^\s+$/.test(tok)) {
                      return <span key={ti}>{tok}</span>;
                    }
                    return (
                      <motion.span
                        key={ti}
                        variants={{
                          hidden: { opacity: 0, y: 8, filter: "blur(4px)" },
                          show: {
                            opacity: 1,
                            y: 0,
                            filter: "blur(0px)",
                            transition: { duration: 0.32, ease: "easeOut" },
                          },
                        }}
                        className="inline-block"
                      >
                        {tok}
                      </motion.span>
                    );
                  })}
                </motion.span>
                {(isActive || (isFinal && done)) && (
                  <Cursor pulse={isFinal && done} />
                )}
              </motion.p>
            );
          })}
        </AnimatePresence>
      </div>

      {!done && (
        <motion.button
          type="button"
          onClick={handleSkip}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="absolute right-0 top-0 inline-flex items-center gap-1 rounded-md border hairline bg-surface/70 px-2 py-1 text-[10.5px] uppercase tracking-wider text-text-dim backdrop-blur transition-colors hover:border-[rgba(255,106,31,0.4)] hover:text-[#ffb380]"
          aria-label="Skip intro"
        >
          <SkipForward className="h-3 w-3" />
          Skip
        </motion.button>
      )}
    </div>
  );
}

function Cursor({ pulse }: { pulse: boolean }) {
  return (
    <motion.span
      aria-hidden="true"
      initial={{ opacity: 1 }}
      animate={{ opacity: pulse ? [1, 0.15, 1] : [1, 0, 1] }}
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
