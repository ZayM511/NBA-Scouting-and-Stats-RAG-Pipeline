"use client";

import { motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart3,
  Crosshair,
  Flame,
  ShieldHalf,
  Sparkles,
  Trophy,
  Wind,
  Zap,
} from "lucide-react";
import type { Headline } from "@/lib/api";

const TONE_MAP: Record<
  Headline["tone"],
  { color: string; bg: string; ring: string; Icon: typeof Sparkles }
> = {
  ember: { color: "#ffb380", bg: "rgba(255,106,31,0.10)", ring: "rgba(255,106,31,0.40)", Icon: Flame },
  ice: { color: "#7dd3fc", bg: "rgba(125,211,252,0.10)", ring: "rgba(125,211,252,0.40)", Icon: Wind },
  emerald: { color: "#6ee7b7", bg: "rgba(52,211,153,0.10)", ring: "rgba(52,211,153,0.40)", Icon: BarChart3 },
  violet: { color: "#c4b5fd", bg: "rgba(167,139,250,0.12)", ring: "rgba(167,139,250,0.45)", Icon: Crosshair },
  rose: { color: "#fda4af", bg: "rgba(251,113,133,0.10)", ring: "rgba(251,113,133,0.42)", Icon: ShieldHalf },
  amber: { color: "#fcd34d", bg: "rgba(251,191,36,0.10)", ring: "rgba(251,191,36,0.45)", Icon: Trophy },
};

interface Props {
  headlines: Headline[];
  /** Pixels per second; the duration auto-derives from card width. */
  speed?: number;
}

/**
 * HeaderTicker — infinite-scroll marquee of stat cards.
 *
 * The cards array is duplicated end-to-end, then animated from 0 to -50% on
 * the X axis with linear easing — at any moment the second copy is replacing
 * the first as it scrolls off, creating a seamless loop. Hovering pauses the
 * animation so you can actually read the card under your cursor.
 */
export function HeaderTicker({ headlines, speed = 38 }: Props) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [trackWidth, setTrackWidth] = useState(0);

  // Measure half the track (one copy worth) so the animation duration scales
  // with content, keeping speed consistent regardless of how many headlines
  // the backend returns today.
  useEffect(() => {
    if (!trackRef.current) return;
    const observer = new ResizeObserver(() => {
      if (!trackRef.current) return;
      setTrackWidth(trackRef.current.scrollWidth / 2);
    });
    observer.observe(trackRef.current);
    return () => observer.disconnect();
  }, [headlines.length]);

  // Duplicate headlines for the seamless loop.
  const doubled = useMemo(() => [...headlines, ...headlines], [headlines]);
  const duration = trackWidth > 0 ? trackWidth / speed : 30;

  if (headlines.length === 0) {
    return (
      <div className="text-[11px] uppercase tracking-[0.18em] text-text-dim">
        Loading league stats…
      </div>
    );
  }

  return (
    <div
      data-testid="header-ticker"
      className="group relative h-full overflow-hidden"
      style={{
        maskImage:
          "linear-gradient(90deg, transparent 0%, #000 6%, #000 94%, transparent 100%)",
        WebkitMaskImage:
          "linear-gradient(90deg, transparent 0%, #000 6%, #000 94%, transparent 100%)",
      }}
      aria-label="NBA scrolling stat ticker"
      role="region"
    >
      <motion.div
        ref={trackRef}
        data-testid="header-ticker-track"
        className="flex h-full w-max items-center gap-3 will-change-transform"
        animate={{ x: trackWidth > 0 ? -trackWidth : 0 }}
        transition={{
          duration,
          ease: "linear",
          repeat: Infinity,
        }}
        style={{ pointerEvents: "auto" }}
      >
        {doubled.map((h, i) =>
          h.kind === "divider" ? (
            <TickerDivider key={`${h.label}-${i}`} headline={h} />
          ) : (
            <TickerCard key={`${h.label}-${i}`} headline={h} />
          ),
        )}
      </motion.div>

      <style>{`
        .group:hover [class*="will-change-transform"] {
          animation-play-state: paused;
        }
      `}</style>
    </div>
  );
}

function TickerCard({ headline }: { headline: Headline }) {
  const tone = TONE_MAP[headline.tone] ?? TONE_MAP.ember;
  const Icon = tone.Icon;
  return (
    <motion.div
      whileHover={{ y: -1, scale: 1.01 }}
      className="flex shrink-0 items-center gap-2 rounded-full border bg-surface/65 px-3 py-1 backdrop-blur-md"
      style={{ borderColor: tone.ring, boxShadow: `inset 0 0 0 1px ${tone.ring}, 0 6px 18px -10px rgba(0,0,0,0.5)` }}
    >
      <span
        className="inline-flex h-5 w-5 items-center justify-center rounded-full"
        style={{ background: tone.bg, color: tone.color }}
      >
        <Icon className="h-3 w-3" />
      </span>
      <span
        className="text-[9px] font-semibold uppercase tracking-[0.18em] whitespace-nowrap"
        style={{ color: tone.color }}
      >
        {headline.label}
      </span>
      <span className="h-3 w-px bg-white/10" aria-hidden="true" />
      <span className="text-[12px] font-medium text-text whitespace-nowrap">
        {headline.primary}
      </span>
      <span className="text-[11px] text-text-dim whitespace-nowrap">
        {headline.secondary}
      </span>
      <span
        className="rounded-md px-1.5 py-0.5 font-mono text-[10.5px] font-semibold whitespace-nowrap"
        style={{ background: tone.bg, color: tone.color }}
      >
        {headline.metric}
      </span>
    </motion.div>
  );
}

/**
 * TickerDivider — wider, taller "section header" pill that the marquee
 * renders between groups (Awards, Leaders, Stats, Upcoming, Fun Facts).
 * Carries only the label — no metric, no secondary, no primary.
 */
function TickerDivider({ headline }: { headline: Headline }) {
  const tone = TONE_MAP[headline.tone] ?? TONE_MAP.ember;
  const Icon = tone.Icon;
  return (
    <motion.div
      data-testid="ticker-divider"
      className="flex shrink-0 items-center gap-2 rounded-full border bg-surface/85 px-4 py-1.5 backdrop-blur-md"
      style={{
        borderColor: tone.ring,
        boxShadow: `inset 0 0 0 1px ${tone.ring}, 0 6px 18px -10px rgba(0,0,0,0.5)`,
        background: `linear-gradient(90deg, ${tone.bg} 0%, rgba(255,255,255,0.02) 50%, ${tone.bg} 100%)`,
      }}
    >
      <span
        className="inline-flex h-5 w-5 items-center justify-center rounded-full"
        style={{ background: tone.bg, color: tone.color }}
      >
        <Icon className="h-3.5 w-3.5" />
      </span>
      <span
        className="text-[13px] font-bold uppercase tracking-[0.20em] whitespace-nowrap"
        style={{ color: tone.color }}
      >
        {headline.label}
      </span>
      <span
        aria-hidden="true"
        className="ml-1 inline-flex h-1 w-1 rounded-full"
        style={{ background: tone.color, boxShadow: `0 0 8px ${tone.color}` }}
      />
    </motion.div>
  );
}


/**
 * StaticTickerStrip — non-marquee fallback for situations where the parent
 * isn't wide enough to scroll. Renders a single row.
 */
export function StaticTickerStrip({ headlines }: { headlines: Headline[] }) {
  return (
    <div className="flex items-center gap-2 overflow-x-auto">
      {headlines.map((h, i) => (
        <TickerCard key={i} headline={h} />
      ))}
    </div>
  );
}

export { TickerCard };

// Helper re-export for convenience
export { Zap };
