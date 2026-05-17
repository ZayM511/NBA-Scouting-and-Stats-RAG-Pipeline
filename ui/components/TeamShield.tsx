"use client";

import { motion } from "framer-motion";
import type { TeamLite } from "@/lib/api";
import { cn } from "@/lib/cn";

interface Props {
  team: TeamLite;
  size?: "sm" | "md" | "lg";
  rotate?: number;
  /** Direction the diagonal split runs. left → primary on left, right → on right. */
  side?: "left" | "right";
}

const SIZES = {
  sm: { box: "h-10 w-10", abbr: "text-[11px]" },
  md: { box: "h-14 w-14", abbr: "text-[13px]" },
  lg: { box: "h-20 w-20", abbr: "text-[18px]" },
};

/**
 * TeamShield — diagonal-split SVG badge in the team's two brand colors,
 * with the three-letter abbreviation centered.
 *
 * No external imagery (no team logo PNGs needed), no AI generation, fully
 * sharp at every size. The split direction can be flipped so matchup pairs
 * mirror each other.
 */
export function TeamShield({ team, size = "md", rotate = 0, side = "left" }: Props) {
  const s = SIZES[size];
  const split = side === "left" ? 1 : -1;
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.92, rotate: rotate - 6 * split }}
      animate={{ opacity: 1, scale: 1, rotate }}
      transition={{ type: "spring", stiffness: 200, damping: 18 }}
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center rounded-2xl border border-white/10 shadow-[0_10px_30px_-12px_rgba(0,0,0,0.7)]",
        s.box,
      )}
    >
      <svg
        viewBox="0 0 60 60"
        className="absolute inset-0 h-full w-full overflow-hidden rounded-2xl"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id={`grad-${team.abbr}-${side}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={team.primary} />
            <stop offset="100%" stopColor={team.secondary} stopOpacity="0.92" />
          </linearGradient>
        </defs>
        <rect width="60" height="60" fill={`url(#grad-${team.abbr}-${side})`} />
        {/* Diagonal split */}
        <polygon
          points={side === "left" ? "0,0 60,0 60,60" : "0,0 60,0 0,60"}
          fill={team.secondary}
          opacity="0.55"
        />
        {/* Subtle glossy top sheen */}
        <rect width="60" height="22" fill="white" opacity="0.10" />
        {/* Inner ring */}
        <rect
          x="2"
          y="2"
          width="56"
          height="56"
          rx="11"
          fill="none"
          stroke="white"
          strokeOpacity="0.12"
          strokeWidth="1"
        />
      </svg>
      <span
        className={cn(
          "relative z-10 font-mono font-bold tracking-wider text-white",
          s.abbr,
        )}
        style={{ textShadow: "0 1px 2px rgba(0,0,0,0.55)" }}
      >
        {team.abbr}
      </span>
    </motion.div>
  );
}
