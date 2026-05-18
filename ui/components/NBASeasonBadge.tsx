"use client";

import Image from "next/image";
import { motion } from "framer-motion";

/**
 * NBASeasonBadge — prominent pill with a zoomed-in NBA logo card on the
 * left and "NBA 2025-26 SEASON" stacked text on the right. The inner
 * image is rendered at scale(1.25) and centered inside an overflow-hidden
 * container so the figure visually fills the card edge-to-edge (no empty
 * left/right margins) without changing the card's outer dimensions.
 */
export function NBASeasonBadge() {
  return (
    <motion.div
      data-testid="nba-season-badge"
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut", delay: 0.05 }}
      className="relative inline-flex h-16 items-center gap-2 rounded-xl border hairline-strong bg-surface/65 pl-2 pr-3 py-2 backdrop-blur-xl shadow-[0_10px_30px_-12px_rgba(0,0,0,0.6)]"
    >
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 rounded-xl"
        style={{
          background:
            "linear-gradient(90deg, rgba(0,107,182,0.14) 0%, rgba(255,255,255,0) 35%, rgba(237,23,76,0.14) 100%)",
        }}
      />
      <div
        data-testid="nba-logo-card"
        className="relative flex h-12 w-8 items-center justify-center overflow-hidden rounded-md bg-white shadow-[inset_0_-2px_4px_rgba(0,0,0,0.08)]"
      >
        <Image
          data-testid="nba-logo-image"
          src="/nba-logo.png"
          alt="NBA"
          width={60}
          height={86}
          className="h-full w-auto object-cover object-center"
          style={{ transform: "scale(1.05)", transformOrigin: "center" }}
          priority
        />
      </div>
      <span className="relative whitespace-nowrap text-[13px] font-semibold uppercase tracking-[0.14em] text-text">
        <span className="text-text-muted">NBA</span>{" "}
        <span className="ember-text">2025–26</span>{" "}
        <span className="text-text-muted">Season</span>
      </span>
    </motion.div>
  );
}
