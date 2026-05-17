"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Clock, Crown, Flame, MapPin, Radio, Trophy } from "lucide-react";
import { TeamShield } from "./TeamShield";
import type { LiveGame, RecentGame, UpcomingGame } from "@/lib/api";

// --------------------------------------------------------------------------
// Time helpers
// --------------------------------------------------------------------------

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
    weekday: "short",
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

// --------------------------------------------------------------------------
// Upcoming
// --------------------------------------------------------------------------

interface UpcomingProps {
  game: UpcomingGame;
}

export function UpcomingMatchupBanner({ game }: UpcomingProps) {
  const userTz = useMemo(userTimeZone, []);
  const [countdown, setCountdown] = useState(() => formatCountdown(game.tipoff_utc));

  useEffect(() => {
    const t = setInterval(() => setCountdown(formatCountdown(game.tipoff_utc)), 1000);
    return () => clearInterval(t);
  }, [game.tipoff_utc]);

  const userTime = formatTipoff(game.tipoff_utc, userTz);
  const arenaTime = formatTipoff(game.tipoff_utc, game.arena_timezone);
  const sameZone = userTime === arenaTime;

  return (
    <motion.div
      key="upcoming"
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="relative flex w-full items-center gap-4 overflow-hidden rounded-2xl border bg-surface/55 px-4 py-2 backdrop-blur-xl"
      style={{
        borderColor: "rgba(255,255,255,0.10)",
        background: `linear-gradient(90deg, ${hexA(game.away.primary, 0.18)} 0%, rgba(7,7,10,0.55) 35%, rgba(7,7,10,0.55) 65%, ${hexA(game.home.primary, 0.18)} 100%)`,
      }}
    >
      <Sweep />

      <div className="hidden flex-col gap-0.5 md:flex">
        <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.22em] text-[#ffb380]">
          <Flame className="h-3 w-3" />
          {game.label}
        </span>
        <span className="text-[10px] uppercase tracking-[0.15em] text-text-dim">
          {game.series_state ?? ""}
        </span>
      </div>

      <div className="relative ml-auto flex items-center gap-3">
        <div className="flex items-center gap-2 text-right">
          <div className="flex flex-col items-end leading-tight">
            <span className="text-[10px] uppercase tracking-wider text-text-dim">{game.away.city}</span>
            <span className="text-[13px] font-semibold text-text">{game.away.name}</span>
          </div>
          <TeamShield team={game.away} side="left" size="md" rotate={-3} />
        </div>

        <div className="flex flex-col items-center gap-0.5 px-2">
          <span className="font-mono text-[11px] uppercase tracking-wider text-text-dim">VS</span>
          <motion.span
            key={countdown}
            initial={{ opacity: 0.5, scale: 0.94 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.18 }}
            className="rounded-md border border-[rgba(255,106,31,0.45)] bg-[rgba(255,106,31,0.10)] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#ffb380]"
          >
            {countdown}
          </motion.span>
        </div>

        <div className="flex items-center gap-2">
          <TeamShield team={game.home} side="right" size="md" rotate={3} />
          <div className="flex flex-col items-start leading-tight">
            <span className="text-[10px] uppercase tracking-wider text-text-dim">{game.home.city}</span>
            <span className="text-[13px] font-semibold text-text">{game.home.name}</span>
          </div>
        </div>
      </div>

      <div className="ml-3 hidden flex-col items-end gap-0.5 border-l border-white/10 pl-3 lg:flex">
        <span className="inline-flex items-center gap-1 text-[10.5px] text-text-muted">
          <Clock className="h-3 w-3" /> {userTime}{" "}
          <span className="text-text-dim">(your time)</span>
        </span>
        {!sameZone && (
          <span className="inline-flex items-center gap-1 text-[10.5px] text-text-dim">
            <MapPin className="h-3 w-3" /> {arenaTime} · {game.arena}
          </span>
        )}
      </div>
    </motion.div>
  );
}

// --------------------------------------------------------------------------
// Live
// --------------------------------------------------------------------------

interface LiveProps {
  game: LiveGame;
}

export function LiveGameBanner({ game }: LiveProps) {
  return (
    <motion.div
      key="live"
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="relative flex w-full items-center gap-4 overflow-hidden rounded-2xl border bg-surface/55 px-4 py-2 backdrop-blur-xl"
      style={{
        borderColor: "rgba(255,255,255,0.10)",
        background: `linear-gradient(90deg, ${hexA(game.away.primary, 0.22)} 0%, rgba(7,7,10,0.55) 35%, rgba(7,7,10,0.55) 65%, ${hexA(game.home.primary, 0.22)} 100%)`,
      }}
    >
      <Sweep />

      <div className="hidden flex-col gap-0.5 md:flex">
        <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.22em] text-[#fb7185]">
          <span className="relative inline-flex">
            <span className="absolute inline-flex h-2 w-2 animate-ping rounded-full bg-rose-400 opacity-75" />
            <Radio className="h-3 w-3" />
          </span>
          {game.label}
        </span>
        <span className="text-[10px] uppercase tracking-[0.15em] text-text-dim">
          Q{game.quarter} · {game.clock}
        </span>
      </div>

      <div className="relative ml-auto flex items-center gap-3">
        <div className="flex items-center gap-2 text-right">
          <div className="flex flex-col items-end leading-tight">
            <span className="text-[10px] uppercase tracking-wider text-text-dim">{game.away.city}</span>
            <span className="text-[13px] font-semibold text-text">{game.away.name}</span>
          </div>
          <TeamShield team={game.away} side="left" size="md" rotate={-3} />
          <span
            className={`font-mono text-[20px] font-bold tabular-nums ${game.away_score > game.home_score ? "text-[#ffb380]" : "text-text"}`}
          >
            {game.away_score}
          </span>
        </div>

        <span className="text-[12px] text-text-dim">·</span>

        <div className="flex items-center gap-2">
          <span
            className={`font-mono text-[20px] font-bold tabular-nums ${game.home_score > game.away_score ? "text-[#ffb380]" : "text-text"}`}
          >
            {game.home_score}
          </span>
          <TeamShield team={game.home} side="right" size="md" rotate={3} />
          <div className="flex flex-col items-start leading-tight">
            <span className="text-[10px] uppercase tracking-wider text-text-dim">{game.home.city}</span>
            <span className="text-[13px] font-semibold text-text">{game.home.name}</span>
          </div>
        </div>
      </div>

      <div className="ml-3 hidden flex-col items-end gap-0.5 border-l border-white/10 pl-3 lg:flex">
        {game.leaders.slice(0, 2).map((leader) => (
          <span key={leader.name} className="inline-flex items-center gap-1.5 text-[10.5px] text-text-muted">
            <Trophy className="h-3 w-3 text-[#fcd34d]" />
            <span className="text-text">{leader.name}</span>
            <span className="text-text-dim">·</span>
            <span className="font-mono text-text-muted">{leader.line}</span>
          </span>
        ))}
        {game.highlight && (
          <span className="text-[10px] italic text-text-dim">{game.highlight}</span>
        )}
      </div>
    </motion.div>
  );
}

// --------------------------------------------------------------------------
// Recap
// --------------------------------------------------------------------------

interface RecapProps {
  game: RecentGame;
}

export function RecapBanner({ game }: RecapProps) {
  const homeWon = game.home_score > game.away_score;
  return (
    <motion.div
      key="recap"
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="relative flex w-full items-center gap-4 overflow-hidden rounded-2xl border bg-surface/55 px-4 py-2 backdrop-blur-xl"
      style={{
        borderColor: "rgba(255,255,255,0.10)",
        background: `linear-gradient(90deg, ${hexA(game.away.primary, 0.18)} 0%, rgba(7,7,10,0.55) 35%, rgba(7,7,10,0.55) 65%, ${hexA(game.home.primary, 0.18)} 100%)`,
      }}
    >
      <Sweep />
      <div className="hidden flex-col gap-0.5 md:flex">
        <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.22em] text-[#7dd3fc]">
          <Crown className="h-3 w-3" />
          {game.label}
        </span>
        <span className="text-[10px] uppercase tracking-[0.15em] text-text-dim">
          {new Date(`${game.date}T12:00:00`).toLocaleDateString(undefined, {
            weekday: "short",
            month: "short",
            day: "numeric",
          })}
        </span>
      </div>

      <div className="relative ml-auto flex items-center gap-3">
        <div className="flex items-center gap-2 text-right">
          <span
            className={`font-mono text-[18px] font-semibold tabular-nums ${!homeWon ? "text-[#ffb380]" : "text-text-dim"}`}
          >
            {game.away_score}
          </span>
          <TeamShield team={game.away} side="left" size="sm" rotate={-2} />
          <span className="text-[12px] text-text-muted">{game.away.abbr}</span>
        </div>
        <span className="font-mono text-[11px] uppercase tracking-wider text-text-dim">FINAL</span>
        <div className="flex items-center gap-2">
          <span className="text-[12px] text-text-muted">{game.home.abbr}</span>
          <TeamShield team={game.home} side="right" size="sm" rotate={2} />
          <span
            className={`font-mono text-[18px] font-semibold tabular-nums ${homeWon ? "text-[#ffb380]" : "text-text-dim"}`}
          >
            {game.home_score}
          </span>
        </div>
      </div>

      {game.leaders.length > 0 && (
        <div className="ml-3 hidden flex-col items-end gap-0.5 border-l border-white/10 pl-3 lg:flex">
          {game.leaders.slice(0, 2).map((l) => (
            <span key={l.name} className="text-[10.5px]">
              <span className="text-text">{l.name}</span>{" "}
              <span className="text-text-dim">· {l.line}</span>
            </span>
          ))}
        </div>
      )}
    </motion.div>
  );
}

// --------------------------------------------------------------------------
// Visual helpers
// --------------------------------------------------------------------------

function Sweep() {
  return (
    <motion.div
      aria-hidden="true"
      className="pointer-events-none absolute inset-y-0 -left-1/4 w-1/2 opacity-25"
      initial={{ x: "-20%" }}
      animate={{ x: "240%" }}
      transition={{ duration: 5.2, repeat: Infinity, ease: "easeInOut" }}
      style={{
        background:
          "linear-gradient(110deg, transparent 30%, rgba(255,255,255,0.16) 50%, transparent 70%)",
      }}
    />
  );
}

/** Convert "#RRGGBB" + alpha → "rgba(r,g,b,a)". */
function hexA(hex: string, a: number): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${a})`;
}

export const __test = { hexA, formatCountdown, formatTipoff };
