"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Clock, Crown, Flame, Radio } from "lucide-react";
import { TeamShield } from "./TeamShield";
import type { LiveGame, RecentGame, UpcomingGame } from "@/lib/api";

/**
 * TopRowBanners — slimmer, larger-typeset variants of the matchup banners
 * designed to sit *inside* the top header row alongside the brand title and
 * the NBA 2025-26 badge. The full banners (with leader stat lines and
 * countdown timers in their own column) live in MatchupBanners.tsx and
 * remain available for any future second-row use.
 *
 * Constraints these variants follow:
 *   • Fit within ~480px of horizontal space on a 1480px header without
 *     pushing the title or NBA badge out of the row.
 *   • Use a noticeably larger font for the scores / matchup label so the
 *     state reads at a glance.
 *   • Truncate / hide non-essential decoration on narrower viewports
 *     rather than wrapping or shrinking the core score numbers.
 */

// --- Recap ---------------------------------------------------------------

export function TopRowRecap({ game }: { game: RecentGame }) {
  const homeWon = game.home_score > game.away_score;
  // Normalize the date string into the user's local calendar by anchoring
  // mid-day; otherwise YYYY-MM-DD parses as UTC and slides a day west.
  const dateLabel = new Date(`${game.date}T12:00:00`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
  return (
    <motion.div
      data-testid="top-recap"
      key="recap"
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.3 }}
      className="relative flex h-full items-center gap-3 rounded-xl border border-white/10 bg-surface/55 px-3 backdrop-blur-xl"
      style={{
        background: `linear-gradient(90deg, ${hexA(game.away.primary, 0.20)} 0%, rgba(7,7,10,0.55) 35%, rgba(7,7,10,0.55) 65%, ${hexA(game.home.primary, 0.20)} 100%)`,
      }}
    >
      <Sweep />
      <div className="flex items-center gap-1.5 text-[13px] font-semibold uppercase tracking-[0.16em] text-[#7dd3fc]">
        <Crown className="h-3.5 w-3.5" />
        <span className="hidden xl:inline">{game.label}</span>
        <span className="xl:hidden">FINAL</span>
      </div>
      <div className="flex items-center gap-2">
        <span className={`font-mono text-[22px] font-bold tabular-nums ${!homeWon ? "text-[#ffb380]" : "text-text-muted"}`}>
          {game.away_score}
        </span>
        <TeamShield team={game.away} side="left" size="md" rotate={-2} />
        <span className="text-[11px] uppercase tracking-wider text-text-dim">FINAL</span>
        <TeamShield team={game.home} side="right" size="md" rotate={2} />
        <span className={`font-mono text-[22px] font-bold tabular-nums ${homeWon ? "text-[#ffb380]" : "text-text-muted"}`}>
          {game.home_score}
        </span>
      </div>
      <span className="hidden lg:inline text-[11px] uppercase tracking-[0.18em] text-text-dim">
        · {dateLabel}
      </span>
    </motion.div>
  );
}

// --- Live ----------------------------------------------------------------

export function TopRowLive({ game }: { game: LiveGame }) {
  return (
    <motion.div
      data-testid="top-live"
      key="live"
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.3 }}
      className="relative flex h-full items-center gap-3 rounded-xl border border-[rgba(251,113,133,0.35)] bg-surface/55 px-3 backdrop-blur-xl"
      style={{
        background: `linear-gradient(90deg, ${hexA(game.away.primary, 0.22)} 0%, rgba(7,7,10,0.55) 35%, rgba(7,7,10,0.55) 65%, ${hexA(game.home.primary, 0.22)} 100%)`,
      }}
    >
      <Sweep />
      <div className="flex items-center gap-1.5 text-[13px] font-semibold uppercase tracking-[0.16em] text-[#fb7185]">
        <span className="relative inline-flex h-2.5 w-2.5 shrink-0">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-rose-400 opacity-75" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-rose-400" />
        </span>
        LIVE
        <span className="hidden lg:inline text-text-dim">· Q{game.quarter} {game.clock}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className={`font-mono text-[24px] font-bold tabular-nums ${game.away_score > game.home_score ? "text-[#ffb380]" : "text-text"}`}>
          {game.away_score}
        </span>
        <TeamShield team={game.away} side="left" size="md" rotate={-2} />
        <span className="text-[11px] uppercase tracking-wider text-text-dim">VS</span>
        <TeamShield team={game.home} side="right" size="md" rotate={2} />
        <span className={`font-mono text-[24px] font-bold tabular-nums ${game.home_score > game.away_score ? "text-[#ffb380]" : "text-text"}`}>
          {game.home_score}
        </span>
      </div>
      {game.leaders[0] && (
        <span className="hidden xl:inline truncate max-w-[200px] text-[12px] text-text-muted">
          <span className="text-text">{game.leaders[0].name}</span>
          <span className="text-text-dim"> · {game.leaders[0].line}</span>
        </span>
      )}
    </motion.div>
  );
}

// --- Upcoming ------------------------------------------------------------

function userTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return "UTC";
  }
}

function formatTipoff(iso: string, tz: string): string {
  const d = new Date(iso);
  return new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(d);
}

function formatCountdown(iso: string): string {
  const target = new Date(iso).getTime();
  const now = Date.now();
  let diff = Math.max(0, target - now);
  const h = Math.floor(diff / 3_600_000); diff -= h * 3_600_000;
  const m = Math.floor(diff / 60_000); diff -= m * 60_000;
  const s = Math.floor(diff / 1000);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function TopRowUpcoming({ game }: { game: UpcomingGame }) {
  const userTz = useMemo(userTimeZone, []);
  const [countdown, setCountdown] = useState(() => formatCountdown(game.tipoff_utc));
  useEffect(() => {
    const t = setInterval(() => setCountdown(formatCountdown(game.tipoff_utc)), 1000);
    return () => clearInterval(t);
  }, [game.tipoff_utc]);
  const userTime = formatTipoff(game.tipoff_utc, userTz);

  return (
    <motion.div
      data-testid="top-upcoming"
      key="upcoming"
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.3 }}
      className="relative flex h-full items-center gap-3 rounded-xl border border-[rgba(255,106,31,0.35)] bg-surface/55 px-3 backdrop-blur-xl"
      style={{
        background: `linear-gradient(90deg, ${hexA(game.away.primary, 0.22)} 0%, rgba(7,7,10,0.55) 35%, rgba(7,7,10,0.55) 65%, ${hexA(game.home.primary, 0.22)} 100%)`,
      }}
    >
      <Sweep />
      <div className="flex items-center gap-1.5 text-[13px] font-semibold uppercase tracking-[0.16em] text-[#ffb380]">
        <Flame className="h-3.5 w-3.5" />
        <span className="hidden xl:inline">{game.label}</span>
        <span className="xl:hidden">NEXT GAME</span>
      </div>
      <div className="flex items-center gap-2">
        <TeamShield team={game.away} side="left" size="md" rotate={-2} />
        <span className="text-[18px] font-semibold text-text">{game.away.abbr}</span>
        <span className="text-[11px] uppercase tracking-wider text-text-dim">@</span>
        <span className="text-[18px] font-semibold text-text">{game.home.abbr}</span>
        <TeamShield team={game.home} side="right" size="md" rotate={2} />
      </div>
      <motion.span
        key={countdown}
        initial={{ opacity: 0.5, scale: 0.94 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.18 }}
        className="rounded-md border border-[rgba(255,106,31,0.50)] bg-[rgba(255,106,31,0.12)] px-2 py-0.5 font-mono text-[14px] font-semibold text-[#ffb380]"
      >
        {countdown}
      </motion.span>
      <span className="hidden lg:inline-flex items-center gap-1 text-[12px] text-text-muted">
        <Clock className="h-3.5 w-3.5" />
        {userTime}
      </span>
    </motion.div>
  );
}

// --- Helpers -------------------------------------------------------------

function Sweep() {
  return (
    <motion.div
      aria-hidden="true"
      className="pointer-events-none absolute inset-y-0 -left-1/4 w-1/2 opacity-25"
      initial={{ x: "-20%" }}
      animate={{ x: "240%" }}
      transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
      style={{
        background:
          "linear-gradient(110deg, transparent 30%, rgba(255,255,255,0.16) 50%, transparent 70%)",
      }}
    />
  );
}

function hexA(hex: string, a: number): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${a})`;
}
