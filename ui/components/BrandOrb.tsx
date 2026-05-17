"use client";

import dynamic from "next/dynamic";
import { motion } from "framer-motion";

/**
 * BrandOrb — the header's tiny 3D basketball glyph. Renders the same
 * GLB the home orb uses, just smaller and cheaper:
 *   • dprMax=1 keeps fragment cost low
 *   • subdued=true cools the bloom intensity so the small canvas doesn't
 *     fight the title typography next to it
 *   • pointer-events:none — the surrounding button receives the click
 *
 * The outer motion.div applies the slow rotation the prior SVG BrandMark
 * had, so the orbit feel of the original is preserved.
 */

const BasketballOrb = dynamic(
  () => import("./BasketballOrb").then((m) => m.BasketballOrb),
  { ssr: false, loading: () => null },
);

export function BrandOrb({ size = 44 }: { size?: number }) {
  return (
    <div
      data-testid="brand-orb"
      className="relative shrink-0 pointer-events-none"
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <div
        className="absolute inset-0 rounded-full blur-md"
        style={{
          background:
            "radial-gradient(circle, rgba(255,106,31,0.55) 0%, transparent 70%)",
        }}
      />
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 28, repeat: Infinity, ease: "linear" }}
        className="absolute inset-0"
      >
        <BasketballOrb
          scale={0.9}
          dprMax={1}
          subdued
          className="absolute inset-0 h-full w-full"
        />
      </motion.div>
    </div>
  );
}
