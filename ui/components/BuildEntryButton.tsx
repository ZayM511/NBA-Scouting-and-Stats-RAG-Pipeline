"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { BookOpen, ArrowRight } from "lucide-react";

/**
 * BuildEntryButton — small ember-toned pill that takes the visitor from
 * the home screen to the `/build` page (the "How I Built This" story).
 *
 * Anchored to the top of the trace sidebar (Sidebar renders it above the
 * EmptyTrace card on the home branch only). One-time slide-in on mount so
 * it doesn't fight the "About The Oracle" pulse for attention.
 */
export function BuildEntryButton() {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, ease: "easeOut", delay: 0.2 }}
      className="px-5 pb-3 pt-4"
    >
      <Link
        href="/build"
        data-testid="build-entry-button"
        className="group inline-flex w-full items-center justify-between gap-2 rounded-xl border hairline-strong bg-surface/70 px-3.5 py-2.5 text-[12px] uppercase tracking-[0.16em] text-text-muted backdrop-blur-md transition-colors hover:border-[rgba(255,106,31,0.55)] hover:bg-[rgba(255,106,31,0.08)] hover:text-[#ffb380] focus:outline-none focus-ember"
        aria-label="How I built this — open the build story page"
      >
        <span className="inline-flex items-center gap-2">
          <BookOpen
            className="h-3.5 w-3.5 shrink-0 text-[#ffb380]"
            aria-hidden="true"
          />
          How I Built This
        </span>
        <ArrowRight
          className="h-3.5 w-3.5 shrink-0 text-text-dim transition-transform group-hover:translate-x-0.5 group-hover:text-[#ffb380]"
          aria-hidden="true"
        />
      </Link>
    </motion.div>
  );
}
