"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Compass, Database, GitBranch, Layers, Quote, Search } from "lucide-react";
import type { Turn } from "./TurnCard";
import { RouteBadge } from "./RouteBadge";
import { RetrievalPanel } from "./RetrievalPanel";
import { StatsPanel } from "./StatsPanel";
import { HybridPanel } from "./HybridPanel";

interface Props {
  turn?: Turn;
}

export function Sidebar({ turn }: Props) {
  if (!turn) return <EmptyTrace />;
  if (turn.status === "pending") return <PendingTrace />;
  if (turn.status === "error" || !turn.response) return <EmptyTrace error />;

  const r = turn.response;
  const cited = r.synthesis?.cited_chunk_ids ?? [];

  return (
    <div className="flex h-full flex-col">
      <div className="border-b hairline px-5 py-3.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Compass className="h-3.5 w-3.5 text-text-muted" />
            <span className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
              Trace
            </span>
          </div>
          <RouteBadge route={r.route.route} reasoning={r.route.reasoning} />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={turn.question}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="space-y-5"
          >
            <Section icon={<GitBranch className="h-3 w-3" />} label="Router">
              <p className="text-[12.5px] leading-6 text-text-muted">
                {r.route.reasoning}
              </p>
            </Section>

            {r.retrieval && (
              <Section
                icon={<Search className="h-3 w-3" />}
                label="Retrieval"
                count={r.retrieval.merged_count}
              >
                <RetrievalPanel retrieval={r.retrieval} citedChunkIds={cited} />
              </Section>
            )}

            {r.stats && (
              <Section icon={<Database className="h-3 w-3" />} label="Stats · SQL">
                <StatsPanel stats={r.stats} />
              </Section>
            )}

            {r.hybrid && (
              <Section icon={<Layers className="h-3 w-3" />} label="Hybrid">
                <HybridPanel hybrid={r.hybrid} citedChunkIds={cited} />
              </Section>
            )}

            {cited.length > 0 && (
              <Section
                icon={<Quote className="h-3 w-3" />}
                label="Cited chunks"
                count={cited.length}
              >
                <div className="flex flex-wrap gap-1.5">
                  {cited.map((id) => (
                    <a
                      key={id}
                      href={`#chunk-${id}`}
                      onClick={(e) => {
                        e.preventDefault();
                        document
                          .getElementById(`chunk-${id}`)
                          ?.scrollIntoView({ behavior: "smooth", block: "center" });
                      }}
                      className="rounded-md border hairline bg-surface-2 px-2 py-0.5 font-mono text-[11px] text-text-muted hover:border-[rgba(255,106,31,0.4)] hover:text-[#ffb380]"
                    >
                      #{id}
                    </a>
                  ))}
                </div>
              </Section>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

function Section({
  icon,
  label,
  count,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-2 flex items-center gap-2">
        <span
          className="inline-flex h-5 w-5 items-center justify-center rounded-md border hairline text-text-muted"
          style={{ background: "rgba(255,255,255,0.02)" }}
        >
          {icon}
        </span>
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
          {label}
        </h3>
        {count !== undefined && (
          <span className="ml-auto rounded-md border hairline bg-surface-2 px-1.5 py-px font-mono text-[10px] text-text-muted">
            {count}
          </span>
        )}
      </div>
      {children}
    </section>
  );
}

function EmptyTrace({ error = false }: { error?: boolean }) {
  // The sidebar wrapper is transparent on the home screen so the orb glow
  // extends across the viewport, but the empty-trace messaging itself needs
  // to read as a foreground card rather than blending into the background.
  // Wrap the copy in a solid, bordered panel so it pops in front of the orb.
  return (
    <div className="flex h-full items-center justify-center px-5">
      <div className="flex w-full max-w-[300px] flex-col items-center gap-3 rounded-2xl border hairline-strong bg-bg-elev px-6 py-7 text-center shadow-[0_18px_60px_-20px_rgba(0,0,0,0.85)]">
        <div className="relative h-12 w-12">
          <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle,_rgba(255,106,31,0.30)_0%,_transparent_70%)] blur-xl" />
          <div className="relative grid h-full w-full place-items-center rounded-full border hairline bg-surface-2/80">
            <Compass className="h-5 w-5 text-text-muted" />
          </div>
        </div>
        <p className="text-[12.5px] font-medium text-text-muted">
          {error ? "No trace available." : "The trace will appear here."}
        </p>
        <p className="text-[11.5px] leading-5 text-text-dim">
          Router decisions, retrieved chunks, SQL, and citations land in this
          panel after each question.
        </p>
      </div>
    </div>
  );
}

function PendingTrace() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
      <div className="relative h-10 w-10">
        <div className="orb-pulse absolute inset-0 rounded-full bg-[radial-gradient(circle,_rgba(255,106,31,0.45)_0%,_transparent_70%)]" />
        <div className="relative grid h-full w-full place-items-center rounded-full border hairline-strong bg-surface-2">
          <span
            className="h-2 w-2 animate-pulse rounded-full"
            style={{ background: "#ff6a1f", boxShadow: "0 0 12px #ff6a1f" }}
          />
        </div>
      </div>
      <p className="text-[12.5px] font-medium text-text-muted">Consulting the Oracle…</p>
      <div className="mt-1 w-full max-w-[220px] space-y-1.5">
        <div className="shimmer h-2 w-full rounded" />
        <div className="shimmer h-2 w-10/12 rounded" />
        <div className="shimmer h-2 w-9/12 rounded" />
      </div>
    </div>
  );
}
