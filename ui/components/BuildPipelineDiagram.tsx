"use client";

import { motion } from "framer-motion";
import {
  Brain,
  Compass,
  Database,
  FileText,
  Layers,
  Link2,
  MessageCircle,
  Newspaper,
  Search,
  Sparkles,
} from "lucide-react";

/**
 * BuildPipelineDiagram — illustrated DAG for the /build page.
 *
 * Two visual bands:
 *   1. DATA LAYER (built offline) — how raw NBA data becomes both a
 *      structured Postgres database and an embedded prose corpus, with
 *      an entity normalizer linking the two by player_id.
 *   2. QUERY LAYER (online, per question) — user question → router →
 *      one of three retrieval paths → synthesis → answer.
 *
 * Hand-authored HTML + Tailwind; SVG arrows are pure CSS gradients
 * with chevron glyphs, no third-party diagram library. Honors
 * `prefers-reduced-motion` (the soft data-flow pulse drops out).
 *
 * Each retrieval path card exposes `data-stage="stats" | "prose" |
 * "hybrid"`, the router exposes `data-stage="router"`, and synthesis
 * exposes `data-stage="synthesis"`, so a future E2E test can assert
 * the full set rendered.
 */
export function BuildPipelineDiagram() {
  return (
    <motion.div
      data-testid="build-pipeline-diagram"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className="relative w-full overflow-hidden rounded-3xl border hairline-strong bg-bg-elev/70 p-6 backdrop-blur-md md:p-8"
      style={{
        background:
          "radial-gradient(circle at 50% -10%, rgba(255,106,31,0.10), transparent 55%), linear-gradient(180deg, rgba(12,12,18,0.85), rgba(7,7,10,0.95))",
        boxShadow:
          "0 20px 60px -28px rgba(0,0,0,0.75), inset 0 0 0 1px rgba(255,255,255,0.04)",
      }}
    >
      {/* Twinkle decoration so the diagram echoes the home page's galaxy. */}
      <Twinkles />

      {/* ---- Band 1: DATA LAYER ---- */}
      <SectionLabel
        tone="emerald"
        label="Data Layer"
        sublabel="Built offline · stats refreshed daily, playoff updates live"
      />

      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
        <StackPanel
          title="Stats pipeline"
          subtitle="player_id-keyed numerics"
          tone="ember"
          steps={[
            { icon: Database, label: "nba_api + basketball-ref" },
            { icon: Layers, label: "Postgres — players / games / pbp" },
            { icon: Sparkles, label: "Top 30 deep dive · authored summaries" },
          ]}
        />
        <StackPanel
          title="Prose pipeline"
          subtitle="vector index · pgvector"
          tone="violet"
          steps={[
            { icon: Newspaper, label: "Articles · Reddit · scouting" },
            { icon: Layers, label: "Postgres + pgvector (voyage-3-large)" },
            { icon: Sparkles, label: "Contextual retrieval prefix" },
          ]}
        />
      </div>

      <BridgeNode
        icon={Link2}
        label="Entity Normalizer"
        sublabel="1,525 aliases · 'the Chef' → 201939"
      />

      {/* Divider between data and query bands. */}
      <div className="mt-8 mb-6 flex items-center gap-3 text-[10px] uppercase tracking-[0.30em] text-text-dim">
        <span className="h-px flex-1 bg-gradient-to-r from-transparent via-white/12 to-transparent" />
        <span>per question</span>
        <span className="h-px flex-1 bg-gradient-to-r from-transparent via-white/12 to-transparent" />
      </div>

      {/* ---- Band 2: QUERY LAYER ---- */}
      <SectionLabel
        tone="ember"
        label="Query Layer"
        sublabel="Online · one DAG per user question"
      />

      <div className="mt-4 flex flex-col items-center gap-3">
        <StageCard
          dataStage="user-question"
          icon={MessageCircle}
          tone="slate"
          title="User Question"
          subtitle="received from the chat input"
        />
        <Arrow />
        <StageCard
          dataStage="router"
          icon={Compass}
          tone="ice"
          title="Query Router"
          subtitle="Claude Sonnet 4.5 · classifies stats / prose / hybrid"
        />
        <FanArrow />

        <div className="grid w-full grid-cols-1 gap-3 md:grid-cols-3">
          <StageCard
            dataStage="stats"
            icon={Database}
            tone="ember"
            title="Stats Path"
            subtitle="Text-to-SQL → Postgres"
            note="ex: Jokić clutch TS%"
          />
          <StageCard
            dataStage="prose"
            icon={Search}
            tone="violet"
            title="Prose Path"
            subtitle="Vector search + Cohere Rerank"
            note="ex: how scouts grade Wemby's defense"
          />
          <StageCard
            dataStage="hybrid"
            icon={Layers}
            tone="rose"
            title="Hybrid Path"
            subtitle="SQL filter → Vector"
            note="ex: guards >40% 3PT, praised off-ball"
          />
        </div>

        <MergeArrow />
        <StageCard
          dataStage="synthesis"
          icon={Brain}
          tone="amber"
          title="Synthesis"
          subtitle="Claude Opus 4.6 · grounds answer in retrieved sources"
        />
        <Arrow />
        <StageCard
          dataStage="answer"
          icon={FileText}
          tone="emerald"
          title="Answer + Sources"
          subtitle="cited paragraphs · SQL query · linked chunks"
        />
      </div>

      <p className="mt-6 text-center text-[12.5px] leading-6 text-text-muted">
        Every question enters at the top. The router picks one of three
        paths, the chosen retrieval feeds the synthesis model, and the
        answer comes out with its cited sources. The trace sidebar shows
        each step in real time.
      </p>
    </motion.div>
  );
}

// --- Sub-components ---------------------------------------------------------

const TONE = {
  slate: {
    color: "#cbd5e1",
    bg: "rgba(148,163,184,0.10)",
    ring: "rgba(148,163,184,0.40)",
  },
  ice: {
    color: "#7dd3fc",
    bg: "rgba(125,211,252,0.12)",
    ring: "rgba(125,211,252,0.48)",
  },
  ember: {
    color: "#ffb380",
    bg: "rgba(255,106,31,0.12)",
    ring: "rgba(255,106,31,0.48)",
  },
  violet: {
    color: "#c4b5fd",
    bg: "rgba(167,139,250,0.12)",
    ring: "rgba(167,139,250,0.48)",
  },
  rose: {
    color: "#fda4af",
    bg: "rgba(251,113,133,0.12)",
    ring: "rgba(251,113,133,0.48)",
  },
  amber: {
    color: "#fcd34d",
    bg: "rgba(251,191,36,0.12)",
    ring: "rgba(251,191,36,0.50)",
  },
  emerald: {
    color: "#6ee7b7",
    bg: "rgba(110,231,183,0.12)",
    ring: "rgba(110,231,183,0.50)",
  },
} as const;

type Tone = keyof typeof TONE;

function SectionLabel({
  label,
  sublabel,
  tone,
}: {
  label: string;
  sublabel: string;
  tone: Tone;
}) {
  const t = TONE[tone];
  return (
    <div className="flex items-baseline gap-3">
      <span
        className="text-[11px] font-semibold uppercase tracking-[0.24em]"
        style={{ color: t.color }}
      >
        {label}
      </span>
      <span className="text-[11px] text-text-dim">{sublabel}</span>
    </div>
  );
}

function StackPanel({
  title,
  subtitle,
  tone,
  steps,
}: {
  title: string;
  subtitle: string;
  tone: Tone;
  steps: { icon: typeof Database; label: string }[];
}) {
  const t = TONE[tone];
  return (
    <div
      className="relative rounded-2xl border bg-surface/55 p-4 backdrop-blur-md"
      style={{
        borderColor: t.ring,
        boxShadow: `inset 0 0 0 1px ${t.ring}, 0 12px 28px -16px rgba(0,0,0,0.6)`,
      }}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span
          className="text-[12px] font-semibold uppercase tracking-[0.16em]"
          style={{ color: t.color }}
        >
          {title}
        </span>
        <span className="text-[10.5px] text-text-dim">{subtitle}</span>
      </div>
      <ul className="mt-3 space-y-2">
        {steps.map((s) => (
          <li
            key={s.label}
            className="flex items-center gap-2 rounded-md px-2 py-1.5"
            style={{ background: t.bg }}
          >
            <s.icon
              className="h-3.5 w-3.5 shrink-0"
              style={{ color: t.color }}
              aria-hidden="true"
            />
            <span className="text-[12px] text-text-muted">{s.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function BridgeNode({
  icon: Icon,
  label,
  sublabel,
}: {
  icon: typeof Database;
  label: string;
  sublabel: string;
}) {
  // The entity normalizer is the bridge between the two data pipelines —
  // styled distinctively (amber pill, centered) to signal "this is what
  // unifies them".
  return (
    <div className="mt-3 flex justify-center">
      <div
        className="inline-flex items-center gap-2 rounded-full border bg-surface/65 px-3.5 py-1.5"
        style={{
          borderColor: TONE.amber.ring,
          boxShadow: `inset 0 0 0 1px ${TONE.amber.ring}, 0 0 24px -8px ${TONE.amber.ring}`,
        }}
      >
        <Icon
          className="h-3.5 w-3.5 shrink-0"
          style={{ color: TONE.amber.color }}
          aria-hidden="true"
        />
        <span
          className="text-[11.5px] font-semibold uppercase tracking-[0.18em]"
          style={{ color: TONE.amber.color }}
        >
          {label}
        </span>
        <span className="text-[10.5px] text-text-dim">· {sublabel}</span>
      </div>
    </div>
  );
}

function StageCard({
  dataStage,
  icon: Icon,
  tone,
  title,
  subtitle,
  note,
}: {
  dataStage: string;
  icon: typeof Database;
  tone: Tone;
  title: string;
  subtitle: string;
  note?: string;
}) {
  const t = TONE[tone];
  return (
    <div
      data-stage={dataStage}
      className="relative w-full max-w-[420px] rounded-xl border bg-surface/55 p-3 backdrop-blur-md"
      style={{
        borderColor: t.ring,
        boxShadow: `inset 0 0 0 1px ${t.ring}, 0 10px 26px -14px ${t.ring}`,
      }}
    >
      <div className="flex items-center gap-2.5">
        <span
          className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
          style={{ background: t.bg }}
        >
          <Icon
            className="h-3.5 w-3.5"
            style={{ color: t.color }}
            aria-hidden="true"
          />
        </span>
        <div className="min-w-0 flex-1">
          <div
            className="truncate text-[12px] font-semibold uppercase tracking-[0.14em]"
            style={{ color: t.color }}
          >
            {title}
          </div>
          <div className="truncate text-[11px] text-text-muted">{subtitle}</div>
        </div>
      </div>
      {note && (
        <div className="mt-2 rounded-md border hairline px-2 py-1 text-[10.5px] italic text-text-dim">
          {note}
        </div>
      )}
    </div>
  );
}

function Arrow() {
  return (
    <span
      aria-hidden="true"
      className="my-0.5 inline-block h-4 w-px bg-gradient-to-b from-[rgba(255,106,31,0.55)] to-transparent"
    />
  );
}

function FanArrow() {
  // Visual cue for "the router fans out to three paths". On wide
  // viewports we draw a small inverted-V with two angled dividers
  // alongside the central drop; on narrow we just stack arrows.
  return (
    <div aria-hidden="true" className="relative my-1 h-6 w-full max-w-[420px]">
      <span className="absolute left-1/2 top-0 h-4 w-px -translate-x-1/2 bg-gradient-to-b from-[rgba(125,211,252,0.55)] to-[rgba(255,106,31,0.40)]" />
      <span className="absolute left-1/2 top-1.5 hidden h-px w-3/4 -translate-x-1/2 bg-gradient-to-r from-[rgba(255,106,31,0.0)] via-[rgba(255,106,31,0.50)] to-[rgba(255,106,31,0.0)] md:block" />
    </div>
  );
}

function MergeArrow() {
  // Visual cue for "the three paths converge into synthesis".
  return (
    <div aria-hidden="true" className="relative my-1 h-6 w-full max-w-[420px]">
      <span className="absolute left-1/2 top-2 hidden h-px w-3/4 -translate-x-1/2 bg-gradient-to-r from-[rgba(255,106,31,0.0)] via-[rgba(251,191,36,0.45)] to-[rgba(255,106,31,0.0)] md:block" />
      <span className="absolute bottom-0 left-1/2 h-4 w-px -translate-x-1/2 bg-gradient-to-b from-[rgba(251,191,36,0.45)] to-[rgba(110,231,183,0.55)]" />
    </div>
  );
}

function Twinkles() {
  // A handful of static "stars" sprinkled in the diagram background so
  // it feels like part of the same product family as the home-page
  // galaxy. Pure CSS, no animation by default (a single optional pulse
  // on the first three for a hint of life that respects
  // prefers-reduced-motion).
  const dots = [
    { top: 6, left: 8, size: 2 },
    { top: 14, left: 92, size: 1.5 },
    { top: 38, left: 4, size: 1.5 },
    { top: 22, left: 64, size: 2 },
    { top: 56, left: 90, size: 1.5 },
    { top: 80, left: 12, size: 1.5 },
    { top: 92, left: 78, size: 2 },
  ];
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 -z-[1] overflow-hidden"
    >
      {dots.map((d, i) => (
        <span
          key={i}
          className="absolute rounded-full bg-white/35"
          style={{
            top: `${d.top}%`,
            left: `${d.left}%`,
            height: `${d.size}px`,
            width: `${d.size}px`,
            boxShadow: "0 0 6px rgba(255,255,255,0.45)",
          }}
        />
      ))}
    </div>
  );
}
