"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
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
      <div className="flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-[0.16em] text-[#7dd3fc] whitespace-nowrap">
        <Crown className="h-3.5 w-3.5" />
        <span>{game.label}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className={`font-mono text-[22px] font-bold tabular-nums ${!homeWon ? "text-[#ffb380]" : "text-text-muted"}`}>
          {game.away_score}
        </span>
        <TeamShield team={game.away} side="left" size="md" rotate={0} />
        <div className="flex flex-col items-center leading-tight">
          <span className="text-[10.5px] font-semibold uppercase tracking-wider text-text-dim">
            FINAL
          </span>
          <span className="text-[10.5px] uppercase tracking-wider text-text-dim">
            {dateLabel}
          </span>
        </div>
        <TeamShield team={game.home} side="left" size="md" rotate={0} />
        <span className={`font-mono text-[22px] font-bold tabular-nums ${homeWon ? "text-[#ffb380]" : "text-text-muted"}`}>
          {game.home_score}
        </span>
      </div>
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
      <div className="flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-[0.16em] text-[#fb7185] whitespace-nowrap">
        <span className="relative inline-flex h-2.5 w-2.5 shrink-0">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-rose-400 opacity-75" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-rose-400" />
        </span>
        LIVE
        <span className="text-text-dim">· Q{game.quarter} {game.clock}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className={`font-mono text-[22px] font-bold tabular-nums ${game.away_score > game.home_score ? "text-[#ffb380]" : "text-text"}`}>
          {game.away_score}
        </span>
        <TeamShield team={game.away} side="left" size="md" rotate={0} />
        <span className="text-[10.5px] font-semibold uppercase tracking-wider text-text-dim">VS</span>
        <TeamShield team={game.home} side="left" size="md" rotate={0} />
        <span className={`font-mono text-[22px] font-bold tabular-nums ${game.home_score > game.away_score ? "text-[#ffb380]" : "text-text"}`}>
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

interface CountdownParts {
  d: number;
  h: number;
  m: number;
  s: number;
  totalMs: number;
}

function countdownParts(iso: string): CountdownParts {
  const target = new Date(iso).getTime();
  const totalMs = Math.max(0, target - Date.now());
  let diff = totalMs;
  const d = Math.floor(diff / 86_400_000); diff -= d * 86_400_000;
  const h = Math.floor(diff / 3_600_000); diff -= h * 3_600_000;
  const m = Math.floor(diff / 60_000); diff -= m * 60_000;
  const s = Math.floor(diff / 1000);
  return { d, h, m, s, totalMs };
}


/**
 * CountdownTimer — segmented HH:MM:SS pill cells. Each cell ticks via a
 * framer-motion popLayout swap when the digit changes, so the seconds
 * column counts down smoothly. Days show only when tipoff is more than
 * 24 hours away. Tone tightens to ember within the final hour.
 */
function CountdownTimer({ iso }: { iso: string }) {
  const [parts, setParts] = useState<CountdownParts>(() => countdownParts(iso));
  useEffect(() => {
    setParts(countdownParts(iso));
    const t = setInterval(() => setParts(countdownParts(iso)), 1000);
    return () => clearInterval(t);
  }, [iso]);

  const isImminent = parts.totalMs <= 60 * 60_000 && parts.totalMs > 0;
  const showDays = parts.d > 0;

  return (
    <div
      data-testid="upcoming-countdown"
      className="inline-flex items-center gap-1 rounded-lg border bg-bg-elev/60 px-1.5 py-1 backdrop-blur-md"
      style={{
        borderColor: isImminent
          ? "rgba(251,113,133,0.55)"
          : "rgba(255,106,31,0.45)",
        boxShadow: isImminent
          ? "0 0 0 1px rgba(251,113,133,0.30), 0 8px 24px -10px rgba(251,113,133,0.45)"
          : "0 0 0 1px rgba(255,106,31,0.18), 0 8px 24px -10px rgba(255,106,31,0.30)",
      }}
    >
      {showDays && (
        <>
          <DigitCell value={parts.d} label="D" tone={isImminent ? "rose" : "ember"} />
          <Sep />
        </>
      )}
      <DigitCell
        value={parts.h}
        label={showDays ? "H" : "HR"}
        tone={isImminent ? "rose" : "ember"}
      />
      <Sep />
      <DigitCell value={parts.m} label="M" tone={isImminent ? "rose" : "ember"} />
      <Sep />
      <DigitCell value={parts.s} label="S" tone={isImminent ? "rose" : "ember"} />
    </div>
  );
}

function DigitCell({
  value,
  label,
  tone,
}: {
  value: number;
  label: string;
  tone: "ember" | "rose";
}) {
  const padded = value.toString().padStart(2, "0");
  const color = tone === "rose" ? "#fda4af" : "#ffb380";
  const bg = tone === "rose" ? "rgba(251,113,133,0.10)" : "rgba(255,106,31,0.10)";
  return (
    <span className="relative inline-flex flex-col items-center px-1">
      <span
        className="block min-w-[1.7ch] rounded-md px-1 text-center font-mono text-[15px] font-semibold tabular-nums leading-none"
        style={{ color, background: bg }}
      >
        <AnimatePresence mode="popLayout" initial={false}>
          <motion.span
            key={padded}
            initial={{ y: -8, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 8, opacity: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="block py-0.5"
          >
            {padded}
          </motion.span>
        </AnimatePresence>
      </span>
      <span
        className="mt-0.5 text-[8.5px] uppercase tracking-[0.18em]"
        style={{ color: "rgba(161,161,170,0.85)" }}
      >
        {label}
      </span>
    </span>
  );
}

function Sep() {
  return (
    <span
      className="font-mono text-[15px] font-semibold leading-none"
      style={{ color: "rgba(161,161,170,0.55)" }}
      aria-hidden="true"
    >
      :
    </span>
  );
}

export function TopRowUpcoming({ game }: { game: UpcomingGame }) {
  const userTz = useMemo(userTimeZone, []);
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
      <div className="flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-[0.16em] text-[#ffb380] whitespace-nowrap">
        <Flame className="h-3.5 w-3.5" />
        <span>{game.label}</span>
      </div>
      <div className="flex items-center gap-2">
        <TeamShield team={game.away} side="left" size="md" rotate={0} />
        <span className="text-[18px] font-semibold text-text">{game.away.abbr}</span>
        <span className="text-[10.5px] uppercase tracking-wider text-text-dim">@</span>
        <span className="text-[18px] font-semibold text-text">{game.home.abbr}</span>
        <TeamShield team={game.home} side="left" size="md" rotate={0} />
      </div>
      <CountdownTimer iso={game.tipoff_utc} />
      <span
        data-testid="upcoming-local-time"
        className="hidden lg:inline-flex shrink-0 items-center gap-1 whitespace-nowrap text-[12px] text-text-muted"
      >
        <Clock className="h-3.5 w-3.5 shrink-0" />
        <span className="whitespace-nowrap tabular-nums">{userTime}</span>
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
