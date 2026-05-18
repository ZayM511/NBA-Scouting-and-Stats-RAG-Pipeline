"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { ChevronUp, EyeOff, Layers3 } from "lucide-react";
import { cn } from "@/lib/cn";
import type { HeaderMode, TickerScope } from "@/lib/api";

interface Props {
  current: HeaderMode | "auto";
  onChange: (mode: HeaderMode | "auto") => void;
  scope: TickerScope;
  onScopeChange: (scope: TickerScope) => void;
}

const MODES: { value: HeaderMode | "auto"; label: string; tone: string }[] = [
  { value: "auto", label: "Auto", tone: "text-text-muted" },
  { value: "season", label: "Season ticker", tone: "text-[#ffb380]" },
  { value: "upcoming", label: "Upcoming (24h)", tone: "text-[#7dd3fc]" },
  { value: "live", label: "Live game", tone: "text-[#fb7185]" },
  { value: "recap", label: "Recap", tone: "text-[#c4b5fd]" },
];

/**
 * HeaderStateToggle — small bottom-right floating panel to preview header
 * states without waiting for real games. Defaults to collapsed so it stays
 * out of the way; expand it to switch modes.
 *
 * Below the mode list, a segmented `Playoffs / Regular` control swaps the
 * ticker's leader + stats sections to the chosen scope.
 */
export function HeaderStateToggle({
  current,
  onChange,
  scope,
  onScopeChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState(false);

  if (hidden) return null;

  return (
    <div className="fixed bottom-4 right-4 z-40">
      <AnimatePresence>
        {open && (
          <motion.div
            key="panel"
            initial={{ opacity: 0, y: 6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.98 }}
            transition={{ duration: 0.18 }}
            className="mb-2 w-56 rounded-xl border hairline-strong bg-bg-elev/95 p-1.5 shadow-[0_18px_60px_-20px_rgba(0,0,0,0.85)] backdrop-blur-xl"
          >
            <div className="flex items-center justify-between px-2 pb-1.5 pt-1">
              <span className="text-[10px] uppercase tracking-[0.18em] text-text-dim">
                Header preview
              </span>
              <button
                type="button"
                onClick={() => setHidden(true)}
                aria-label="Hide preview toggle"
                title="Hide preview toggle for this session"
                className="text-text-dim hover:text-text-muted"
              >
                <EyeOff className="h-3 w-3" />
              </button>
            </div>
            <ul className="space-y-0.5">
              {MODES.map((m) => (
                <li key={m.value}>
                  <button
                    type="button"
                    onClick={() => onChange(m.value)}
                    className={cn(
                      "flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-[12px] transition-colors",
                      current === m.value
                        ? "bg-[rgba(255,106,31,0.10)] text-text"
                        : "text-text-muted hover:bg-surface-2 hover:text-text",
                    )}
                  >
                    <span className={current === m.value ? m.tone : ""}>{m.label}</span>
                    {current === m.value && (
                      <span
                        className="h-1.5 w-1.5 rounded-full"
                        style={{ background: "#ff6a1f", boxShadow: "0 0 8px #ff6a1f" }}
                      />
                    )}
                  </button>
                </li>
              ))}
            </ul>

            {/* Ticker scope: regular season vs playoffs. Drives the
                LEADERS + STATS sections of the marquee — Awards, upcoming
                games, and fun facts stay the same either way. */}
            <div className="mt-2 border-t hairline pt-2">
              <div className="px-2 pb-1.5 text-[10px] uppercase tracking-[0.18em] text-text-dim">
                Ticker scope
              </div>
              <div
                role="tablist"
                data-testid="ticker-scope-toggle"
                className="grid grid-cols-2 gap-1 rounded-md border hairline bg-bg-elev/70 p-0.5"
              >
                {(["playoffs", "regular"] as const).map((s) => {
                  const active = scope === s;
                  return (
                    <button
                      key={s}
                      type="button"
                      role="tab"
                      aria-selected={active}
                      data-testid={`ticker-scope-${s}`}
                      onClick={() => onScopeChange(s)}
                      className={cn(
                        "rounded-[5px] px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.10em] transition-colors",
                        active
                          ? "bg-[rgba(255,106,31,0.18)] text-[#ffb380] shadow-[inset_0_0_0_1px_rgba(255,106,31,0.45)]"
                          : "text-text-muted hover:bg-surface-2 hover:text-text",
                      )}
                    >
                      {s === "playoffs" ? "Playoffs" : "Reg. Season"}
                    </button>
                  );
                })}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button
        type="button"
        onClick={() => setOpen((o) => !o)}
        whileHover={{ y: -1 }}
        whileTap={{ scale: 0.96 }}
        aria-label="Header preview modes"
        title="Header preview modes"
        className="inline-flex items-center gap-1.5 rounded-full border hairline-strong bg-bg-elev/85 px-3 py-1.5 text-[11px] uppercase tracking-[0.15em] text-text-muted backdrop-blur-xl shadow-[0_10px_30px_-12px_rgba(0,0,0,0.7)] hover:text-text"
      >
        <Layers3 className="h-3 w-3" />
        <span>
          {current}
          <span className="ml-1 text-text-dim">
            · {scope === "playoffs" ? "PO" : "RS"}
          </span>
        </span>
        <ChevronUp
          className={cn("h-3 w-3 transition-transform", open ? "rotate-180" : "")}
        />
      </motion.button>
    </div>
  );
}
