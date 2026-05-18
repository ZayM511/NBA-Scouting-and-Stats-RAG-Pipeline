"use client";

import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import { ArrowUpRight, BarChart3, Brain, Layers } from "lucide-react";
import { AboutTheOracle } from "./AboutTheOracle";

const BasketballOrb = dynamic(
  () => import("./BasketballOrb").then((m) => m.BasketballOrb),
  { ssr: false, loading: () => <OrbFallback /> },
);

interface Props {
  onSuggestion: (text: string) => void;
  /** Bumped by the parent when the user returns home — resets the about
   *  card and any in-flight animations. */
  runKey?: number;
}

const SUGGESTIONS = [
  {
    icon: BarChart3,
    label: "Stats",
    tone: "emerald" as const,
    q: "Who leads the league in threes this playoffs?",
  },
  {
    icon: Brain,
    label: "Prose",
    tone: "ice" as const,
    q: "How is SGA playing this year?",
  },
  {
    icon: Layers,
    label: "Hybrid",
    tone: "violet" as const,
    q: "Which guards shooting >40% from three move best off-ball?",
  },
];

export function Hero({ onSuggestion, runKey = 0 }: Props) {
  return (
    <div className="relative isolate flex h-full w-full items-center justify-center overflow-hidden px-4">
      <div className="grid-mask absolute inset-0 -z-10 opacity-50" />

      {/* Orb — dominant glowing sun behind the foreground content. */}
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 flex justify-center">
        <div className="relative h-[64vh] w-[64vh] max-h-[700px] max-w-[700px] -mt-[8vh]">
          <div
            className="orb-pulse absolute inset-[-20%] rounded-full blur-3xl"
            style={{
              background:
                "radial-gradient(circle, rgba(255,106,31,0.55) 0%, rgba(255,106,31,0.22) 30%, rgba(255,106,31,0.08) 55%, transparent 75%)",
            }}
          />
          <div
            className="absolute inset-[-10%] rounded-full blur-3xl opacity-40"
            style={{
              background:
                "radial-gradient(circle at 30% 30%, rgba(125,211,252,0.20), transparent 60%)",
            }}
          />
          {/* Golden ambient layer — breathes in sync with the orb's
              in-canvas pulse light to give the edge a warm halo. Pure CSS
              for zero JS cost. */}
          <div
            className="absolute inset-[-15%] rounded-full blur-3xl golden-breath"
            style={{
              background:
                "radial-gradient(circle, rgba(255,210,122,0.42) 0%, rgba(255,210,122,0.18) 35%, transparent 65%)",
            }}
          />
          <BasketballOrb scale={1.0} className="absolute inset-0 h-full w-full" />
        </div>
      </div>

      <style>{`
        @keyframes hero-golden-breath {
          0%, 100% { opacity: 0.55; transform: scale(1); }
          50%      { opacity: 0.95; transform: scale(1.04); }
        }
        .golden-breath { animation: hero-golden-breath 6s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) {
          .golden-breath { animation: none; opacity: 0.7; }
        }
      `}</style>

      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 top-[40%] -z-[5]"
        style={{
          background:
            "linear-gradient(to bottom, transparent 0%, rgba(7,7,10,0.50) 30%, rgba(7,7,10,0.90) 70%, rgba(7,7,10,0.97) 100%)",
        }}
      />

      <div className="relative z-10 mx-auto flex w-full max-w-2xl flex-col items-center gap-3 pt-[22vh] text-center">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="inline-flex items-center gap-2 rounded-full border hairline-strong bg-surface/70 px-3 py-1 text-[11px] uppercase tracking-[0.22em] text-text-muted backdrop-blur"
        >
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: "#ff6a1f", boxShadow: "0 0 10px #ff6a1f" }}
          />
          Hybrid RAG · Stats × Scouting
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.05, ease: "easeOut" }}
          className="text-balance text-3xl font-semibold leading-[1.05] tracking-tight md:text-[2.5rem]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          The <span className="ember-text">Ball Knowledge</span> Oracle
        </motion.h1>

        {/* Compact "About The Oracle" disclosure — replaces the prior
            always-visible Transmission card. Closed by default; clicking
            expands the card and types each statement letter-by-letter. */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.25 }}
          className="flex w-full justify-center"
        >
          <AboutTheOracle runKey={runKey} />
        </motion.div>

        <motion.div
          initial="hidden"
          animate="show"
          variants={{
            hidden: {},
            show: { transition: { staggerChildren: 0.08, delayChildren: 0.45 } },
          }}
          className="flex flex-wrap items-center justify-center gap-2"
        >
          {SUGGESTIONS.map((s) => (
            <motion.button
              key={s.label}
              variants={{
                hidden: { opacity: 0, y: 6 },
                show: { opacity: 1, y: 0 },
              }}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => onSuggestion(s.q)}
              className="group inline-flex items-center gap-2 rounded-full border hairline-strong bg-surface/80 px-3.5 py-1.5 text-left text-[12.5px] text-text-muted backdrop-blur transition-colors hover:border-[rgba(255,106,31,0.4)] hover:text-text"
            >
              <ToneIcon tone={s.tone}>
                <s.icon className="h-3.5 w-3.5" />
              </ToneIcon>
              <span className="whitespace-nowrap">{s.q}</span>
              <ArrowUpRight className="h-3.5 w-3.5 text-text-dim transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </motion.button>
          ))}
        </motion.div>
      </div>
    </div>
  );
}

function ToneIcon({
  tone,
  children,
}: {
  tone: "emerald" | "ice" | "violet";
  children: React.ReactNode;
}) {
  const styles: Record<typeof tone, { color: string; bg: string }> = {
    emerald: { color: "#34d399", bg: "rgba(52,211,153,0.12)" },
    ice: { color: "#7dd3fc", bg: "rgba(125,211,252,0.12)" },
    violet: { color: "#a78bfa", bg: "rgba(167,139,250,0.14)" },
  };
  const s = styles[tone];
  return (
    <span
      className="inline-flex h-6 w-6 items-center justify-center rounded-md"
      style={{ background: s.bg, color: s.color }}
    >
      {children}
    </span>
  );
}

function OrbFallback() {
  return (
    <div className="flex h-full w-full items-center justify-center">
      <div className="orb-pulse h-64 w-64 rounded-full bg-[radial-gradient(circle,_rgba(255,106,31,0.55)_0%,_rgba(255,106,31,0.0)_70%)]" />
    </div>
  );
}
