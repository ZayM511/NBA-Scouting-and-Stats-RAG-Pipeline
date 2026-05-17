"use client";

import { motion } from "framer-motion";

/**
 * BrandMark — small orbital glyph for the header.
 * Two concentric rings + a glowing ember core, slow counter-rotation.
 * Conveys "basketball + oracle" without being literal.
 */
export function BrandMark({ size = 28 }: { size?: number }) {
  const r = size / 2;
  return (
    <div
      style={{ width: size, height: size }}
      className="relative shrink-0"
      aria-hidden="true"
    >
      <div
        className="absolute inset-0 rounded-full blur-md"
        style={{
          background: "radial-gradient(circle, rgba(255,106,31,0.55) 0%, transparent 70%)",
        }}
      />
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <defs>
          <radialGradient id="bm-core" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#fff3eb" />
            <stop offset="40%" stopColor="#ff8a3d" />
            <stop offset="100%" stopColor="#c8480c" />
          </radialGradient>
          <linearGradient id="bm-ring" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#ff6a1f" />
            <stop offset="100%" stopColor="#7dd3fc" />
          </linearGradient>
        </defs>

        <motion.g
          animate={{ rotate: -360 }}
          transition={{ duration: 32, repeat: Infinity, ease: "linear" }}
          style={{ transformOrigin: `${r}px ${r}px` }}
        >
          <circle
            cx={r}
            cy={r}
            r={r - 1.5}
            fill="none"
            stroke="url(#bm-ring)"
            strokeWidth="1"
            strokeDasharray="3 4"
            opacity={0.7}
          />
        </motion.g>

        <motion.g
          animate={{ rotate: 360 }}
          transition={{ duration: 18, repeat: Infinity, ease: "linear" }}
          style={{ transformOrigin: `${r}px ${r}px` }}
        >
          <circle
            cx={r}
            cy={r}
            r={r - 5}
            fill="none"
            stroke="#ff6a1f"
            strokeOpacity={0.6}
            strokeWidth="0.8"
          />
          <circle cx={r + (r - 5)} cy={r} r="1" fill="#ff8a3d" />
        </motion.g>

        <circle cx={r} cy={r} r={r - 9} fill="url(#bm-core)" />
        <path
          d={`M${r - (r - 10)} ${r} Q ${r} ${r - 4} ${r + (r - 10)} ${r}`}
          stroke="#1a0a05"
          strokeWidth="0.7"
          fill="none"
          opacity={0.7}
        />
      </svg>
    </div>
  );
}
