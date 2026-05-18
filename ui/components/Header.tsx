"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Database, Home, Plus } from "lucide-react";
import { BrandMark } from "./BrandMark";
import { NBASeasonBadge } from "./NBASeasonBadge";
import { HeaderTicker } from "./HeaderTicker";
import { TopRowLive, TopRowRecap, TopRowUpcoming } from "./TopRowBanners";
import { HeaderStateToggle } from "./HeaderStateToggle";
import { PipelineProgressBanner } from "./PipelineProgressBanner";
import { getHeader, type HeaderMode, type HeaderPayload } from "@/lib/api";
import { cn } from "@/lib/cn";

interface Props {
  healthOk: boolean | null;
  /** If true, the user is mid-conversation — show the "new chat" affordance. */
  canGoHome: boolean;
  /** Called when the user wants to clear the conversation and return home. */
  onHome: () => void;
  /** When true, a question is in flight — the banner shows pipeline progress. */
  pending?: boolean;
}

export function Header({ healthOk, canGoHome, onHome, pending = false }: Props) {
  const [payload, setPayload] = useState<HeaderPayload | null>(null);
  const [mode, setMode] = useState<HeaderMode | "auto">("auto");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setErr(null);
    getHeader(mode)
      .then((p) => {
        if (!cancelled) setPayload(p);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setErr(e instanceof Error ? e.message : String(e));
          setPayload(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [mode]);

  // Auto-refresh every 60s so live/recap data stays fresh.
  useEffect(() => {
    const t = setInterval(() => {
      getHeader(mode).then(setPayload).catch(() => {});
    }, 60_000);
    return () => clearInterval(t);
  }, [mode]);

  return (
    <>
      <header
        data-testid="app-header"
        className="sticky top-0 z-30 border-b hairline bg-bg/72 backdrop-blur-xl"
      >
        {/* Main row: BKO brand · NBA season badge · state banner · actions.
            Everything sits in one tall row at large type. */}
        <div className="mx-auto flex h-[88px] max-w-[1480px] items-center gap-4 px-5">
          {/* Brand + name (bigger). Acts as a "home" button. */}
          <motion.button
            type="button"
            onClick={onHome}
            data-testid="brand-home"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
            aria-label="Return to home"
            className="group flex shrink-0 items-center gap-3 rounded-xl px-2 py-1.5 -mx-2 transition-colors hover:bg-surface/60 focus:outline-none focus-ember"
          >
            <BrandMark size={44} />
            <div className="flex flex-col items-start leading-tight">
              <span className="text-[20px] font-semibold tracking-tight text-text">
                Ball Knowledge{" "}
                <span className="ember-text">Oracle</span>
              </span>
              <span className="text-[10px] uppercase tracking-[0.22em] text-text-dim">
                NBA Intelligence RAG · 2025–26
              </span>
              <span className="text-[9px] uppercase tracking-[0.22em] text-text-dim/80">
                By Isaiah M.
              </span>
            </div>
          </motion.button>

          {/* Center: NBA season badge geometrically centered in the free
              space between brand and the state banner. */}
          <div className="flex-1" />
          <NBASeasonBadge />
          <div className="flex-1" />

          {/* State banner — h-16 matches the NBA badge height (py-2 + h-12). */}
          <div className="hidden min-w-0 items-center justify-end md:flex">
            <div className="h-16 w-[640px] max-w-[640px]">
              <HeaderStateBanner
                payload={payload}
                err={err}
                pending={pending}
              />
            </div>
          </div>

          {/* Right actions */}
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="flex shrink-0 items-center gap-2"
          >
            {canGoHome && (
              <motion.button
                type="button"
                onClick={onHome}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.25 }}
                whileHover={{ y: -1 }}
                whileTap={{ scale: 0.97 }}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-medium",
                  "border-[rgba(255,106,31,0.35)] bg-[rgba(255,106,31,0.08)] text-[#ffb380]",
                  "transition-colors hover:bg-[rgba(255,106,31,0.14)] hover:border-[rgba(255,106,31,0.55)]",
                  "focus:outline-none focus-ember",
                )}
                aria-label="Start a new chat"
                title="Clear conversation and return to home"
              >
                <Plus className="h-3 w-3" />
                <span>New chat</span>
                <Home className="hidden h-3 w-3 text-text-dim md:inline-flex" />
              </motion.button>
            )}
            <HealthDot healthOk={healthOk} />
          </motion.div>
        </div>

        {/* ESPN-style always-on ticker. Thin strip — never goes away,
            never blocks the row above. */}
        <div
          data-testid="header-ticker-strip"
          className="border-t hairline bg-bg-elev/55"
        >
          <div className="mx-auto h-[34px] max-w-[1480px] px-3 py-1">
            {payload ? (
              <HeaderTicker headlines={payload.headlines} />
            ) : (
              <div className="flex h-full items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-text-dim">
                <span
                  className="inline-flex h-1.5 w-1.5 animate-pulse rounded-full"
                  style={{ background: "#ff6a1f", boxShadow: "0 0 8px #ff6a1f" }}
                />
                Tuning the league…
              </div>
            )}
          </div>
        </div>
      </header>
      <HeaderStateToggle current={mode} onChange={setMode} />
    </>
  );
}

function HeaderStateBanner({
  payload,
  err,
  pending,
}: {
  payload: HeaderPayload | null;
  err: string | null;
  pending: boolean;
}) {
  // Pipeline overrides everything else: while a question is mid-flight,
  // the banner is the user's live status feedback.
  if (pending) {
    return <PipelineProgressBanner pending={pending} />;
  }
  if (err) {
    return (
      <div className="flex h-full items-center text-[11px] text-text-dim">
        Header data unavailable
      </div>
    );
  }
  if (!payload) return null;

  return (
    <AnimatePresence mode="wait" initial={false}>
      {payload.mode === "upcoming" && payload.upcoming ? (
        <TopRowUpcoming key="up" game={payload.upcoming} />
      ) : payload.mode === "live" && payload.live ? (
        <TopRowLive key="live" game={payload.live} />
      ) : payload.mode === "recap" && payload.recent ? (
        <TopRowRecap key="recap" game={payload.recent} />
      ) : (
        <motion.div
          key="season-spacer"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="flex h-full items-center text-[11px] uppercase tracking-[0.18em] text-text-dim"
        >
          {/* Regular-season mode: the stat ticker below carries the
              live league data. Leave this slot quiet. */}
          <span
            className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full"
            style={{ background: "#ff6a1f", boxShadow: "0 0 8px #ff6a1f" }}
          />
          Regular season · stats below
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function HealthDot({ healthOk }: { healthOk: boolean | null }) {
  const state = healthOk === null ? "checking" : healthOk ? "ready" : "down";
  const color =
    state === "ready" ? "#34d399" : state === "down" ? "#fb7185" : "#a1a1aa";
  const label =
    state === "ready" ? "API ready" : state === "down" ? "API down" : "checking";
  return (
    <div className="flex items-center gap-2 rounded-full hairline border px-2.5 py-1 text-[11px] text-text-muted">
      <span className="relative inline-flex h-2 w-2">
        {state === "ready" && (
          <span
            className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
            style={{ background: color }}
          />
        )}
        <span
          className="relative inline-flex h-2 w-2 rounded-full"
          style={{ background: color, boxShadow: `0 0 8px ${color}` }}
        />
      </span>
      <Database className="h-3 w-3 text-text-dim" />
      <span>{label}</span>
    </div>
  );
}
