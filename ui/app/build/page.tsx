import Link from "next/link";
import { ArrowLeft, Code2, Layers, Sparkles, Wrench } from "lucide-react";
import { BrandMark } from "@/components/BrandMark";
import { BuildPipelineDiagram } from "@/components/BuildPipelineDiagram";

const REPO_URL =
  "https://github.com/ZayM511/NBA-Scouting-and-Stats-RAG-Pipeline";
const REPO_BLOB = `${REPO_URL}/blob/main`;

export const metadata = {
  title: "How I Built This · Ball Knowledge Oracle",
  description:
    "The build story behind the Ball Knowledge Oracle: a hybrid stats + scouting RAG system for the 2025-26 NBA season, with query routing across stats, prose, and hybrid paths.",
};

/**
 * /build — the "How I Built This" story page. Server component so the
 * content is search-engine friendly and renders without JS.
 */
export default function BuildPage() {
  return (
    <main className="relative min-h-screen w-full bg-bg text-text">
      {/* Galaxy backdrop, same one the home page uses, kept subtle behind
          long-form content. */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 -z-10"
        style={{
          background:
            "radial-gradient(circle at 50% 0%, rgba(255,106,31,0.10), transparent 60%), radial-gradient(circle at 80% 40%, rgba(125,211,252,0.06), transparent 50%), #07070a",
        }}
      />

      <PageHeader />

      <div className="mx-auto max-w-[860px] px-5 pb-24 pt-8 md:px-8">
        <TitleRow />
        <TLDR />

        <SectionDivider id="architecture" label="Architecture" />
        <BuildPipelineDiagram />

        <SectionDivider id="scope" label="Three tiers of depth" />
        <ScopeTiers />

        <SectionDivider id="build-order" label="Build order" />
        <BuildSteps />

        <SectionDivider id="interesting" label="What's interesting" />
        <InterestingCallouts />

        <SectionDivider id="stack" label="Tech stack" />
        <TechStack />

        <SectionDivider id="next" label="What's next" />
        <WhatsNext />

        <PageFooter />
      </div>
    </main>
  );
}

// --- Page chrome ------------------------------------------------------------

function PageHeader() {
  return (
    <header className="sticky top-0 z-20 border-b hairline bg-bg/72 backdrop-blur-xl">
      <div className="mx-auto flex h-[64px] max-w-[860px] items-center justify-between gap-4 px-5 md:px-8">
        <Link
          href="/"
          className="group inline-flex items-center gap-2 rounded-md px-2 py-1 text-[12px] uppercase tracking-[0.18em] text-text-muted transition-colors hover:text-[#ffb380]"
        >
          <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5" />
          Back to the Oracle
        </Link>

        <Link
          href="/"
          className="flex items-center gap-2"
          aria-label="Ball Knowledge Oracle home"
        >
          <BrandMark size={28} />
          <span className="hidden text-[12.5px] font-semibold tracking-tight md:inline">
            Ball Knowledge <span className="ember-text">Oracle</span>
          </span>
        </Link>

        <a
          href={REPO_URL}
          target="_blank"
          rel="noreferrer"
          data-testid="build-github-link"
          className="group inline-flex items-center gap-2 rounded-md border hairline bg-surface/70 px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] text-text-muted transition-colors hover:border-[rgba(255,106,31,0.45)] hover:text-[#ffb380]"
        >
          <Code2 className="h-3.5 w-3.5" />
          View on GitHub
          <span className="text-text-dim group-hover:text-[#ffb380]">↗</span>
        </a>
      </div>
    </header>
  );
}

function TitleRow() {
  return (
    <div className="mb-8">
      <h1
        className="text-balance text-[34px] font-semibold leading-[1.05] tracking-tight md:text-[44px]"
        style={{ fontFamily: "var(--font-display)" }}
      >
        How I Built <span className="ember-text">This</span>
      </h1>
      <p className="mt-3 max-w-[620px] text-[14.5px] leading-7 text-text-muted">
        A hybrid stats + scouting RAG system for the 2025-26 NBA season,
        built around a single interesting problem: deciding whether a
        question wants a SQL answer, a prose answer, or both.
      </p>
    </div>
  );
}

// --- Content sections -------------------------------------------------------

function TLDR() {
  return (
    <div className="space-y-4 rounded-2xl border hairline bg-surface/40 p-5 backdrop-blur-md md:p-6">
      <div className="flex items-center gap-2 text-[10.5px] uppercase tracking-[0.22em] text-[#ffb380]">
        <Sparkles className="h-3 w-3" />
        TL;DR
      </div>
      <p className="text-[14.5px] leading-7 text-text">
        The Ball Knowledge Oracle covers the entire 2025-26 NBA season in
        three tiers: full season stats for every active player, deep
        scouting analysis on the top 30, and live-updating playoff data
        through the Finals. A Claude Sonnet 4.5 query router decides
        whether a question wants numbers, prose, or both, dispatches the
        retrieval, and a Claude Opus 4.6 synthesis model answers with
        cited paragraphs and the exact SQL that ran.
      </p>
      <p className="text-[13.5px] leading-7 text-text-muted">
        Below: the architecture, the three tiers of scope, the order I
        built things in, what turned out to be interesting (and what
        turned out to be the unsexy gold), and the tech stack.
      </p>
    </div>
  );
}

function ScopeTiers() {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <TierCard
        tier="Tier 1"
        title="All active players"
        tone="emerald"
        count="≈ 500"
        body="Full season stats, game logs, biographical data in Postgres. Nothing fancy, just complete coverage so a stats question about any active player has data to chew on."
      />
      <TierCard
        tier="Tier 2"
        title="Top 30 deep dive"
        tone="ember"
        count="30 players"
        body="Advanced splits — clutch, on/off, lineup data, shot charts — plus hand-picked scouting articles and a Claude-authored 500-word scouting summary per player."
      />
      <TierCard
        tier="Tier 3"
        title="Playoffs (live)"
        tone="rose"
        count="daily refresh"
        body="The playoffs are happening as the demo runs. A daily refresh pulls new game data and articles; time-aware retrieval boosts recent content so a question asked today sees today's evidence."
      />
    </div>
  );
}

function TierCard({
  tier,
  title,
  tone,
  count,
  body,
}: {
  tier: string;
  title: string;
  tone: "emerald" | "ember" | "rose";
  count: string;
  body: string;
}) {
  const COLOR = {
    emerald: "#6ee7b7",
    ember: "#ffb380",
    rose: "#fda4af",
  } as const;
  const c = COLOR[tone];
  return (
    <div
      className="rounded-2xl border bg-surface/55 p-4 backdrop-blur-md"
      style={{
        borderColor: `${c}55`,
        boxShadow: `inset 0 0 0 1px ${c}33`,
      }}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span
          className="text-[10px] font-semibold uppercase tracking-[0.18em]"
          style={{ color: c }}
        >
          {tier}
        </span>
        <span className="font-mono text-[10.5px] text-text-dim">{count}</span>
      </div>
      <h3 className="mt-1 text-[15px] font-semibold text-text">{title}</h3>
      <p className="mt-2 text-[12.5px] leading-6 text-text-muted">{body}</p>
    </div>
  );
}

function BuildSteps() {
  return (
    <ol className="space-y-4">
      <Step
        n={1}
        title="Stats ingestion"
        link={`${REPO_BLOB}/src/ingest_stats`}
        linkLabel="src/ingest_stats"
      >
        <p>
          <code>nba_api</code> is the Python wrapper around the official
          stats.nba.com endpoints — player game logs, advanced stats,
          play-by-play, lineup data. A daily APScheduler job inside the
          FastAPI server refreshes the live scoreboard and the next 14 days
          of upcoming games so the demo stays current through the Finals.
        </p>
      </Step>
      <Step
        n={2}
        title="Stats schema in Postgres"
        link={`${REPO_BLOB}/src/ingest_stats/schema.sql`}
        linkLabel="schema.sql"
      >
        <p>
          Players, games, player_game_stats, and play_by_play (top 30 only,
          because pbp explodes in row count). The interesting field is
          <code> is_clutch_data </code> — a flag that lets clutch-specific
          questions narrow to the clutch sub-table without scanning the
          whole season.
        </p>
      </Step>
      <Step
        n={3}
        title="Prose ingestion"
        link={`${REPO_BLOB}/src/ingest_prose`}
        linkLabel="src/ingest_prose"
      >
        <p>
          Articles and Reddit threads scraped politely (robots.txt, no
          OAuth — Reddit's public <code>.json</code> endpoints are enough).
          Aim was ~500-1000 chunks tagged with date, mentioned players, and
          source. Today's corpus has 197 Reddit threads (257 chunks)
          covering r/nba and team subs.
        </p>
      </Step>
      <Step
        n={4}
        title="Entity normalization"
        link={`${REPO_BLOB}/src/ingest_prose/entities.py`}
        linkLabel="entities.py"
        unsexy
      >
        <p>
          Every name variant resolves to a canonical{" "}
          <code>player_id</code>: "Steph", "Curry", "the Chef",
          "Wardell" all map to 201939. The map has 1,525 aliases today;
          90%+ coverage of the active roster, 100% on the top 30. Every
          scraped chunk runs through this normalizer before embedding so
          a player filter at retrieval time is a single integer match
          instead of a fuzzy string game.
        </p>
        <p className="text-text-dim">
          Why "unsexy gold": entity linking is a real production problem
          every sports data company solves. Pointing at this in
          interviews signals "I've shipped data systems", not "I followed
          a RAG tutorial".
        </p>
      </Step>
      <Step
        n={5}
        title="Embed + index"
        link={`${REPO_BLOB}/src/ingest_prose/embedder.py`}
        linkLabel="embedder.py"
      >
        <p>
          Chunks are 400 tokens with 15% overlap. Voyage{" "}
          <code>voyage-3-large</code> (1024-dim) embeddings, stored in the
          same Postgres DB via pgvector. Contextual-retrieval prefix
          ({`"Article from {source}, {date}, about {players}: …"`}) is
          prepended before embedding for a 35-50% recall lift on hard
          queries.
        </p>
      </Step>
      <Step
        n={6}
        title="Top 30 deep dive"
        link={`${REPO_BLOB}/src/ingest_prose/authored_summaries.py`}
        linkLabel="authored_summaries.py"
      >
        <p>
          For each top-30 player, a one-time enrichment job pulls every
          chunk mentioning them and asks Claude Opus to write a 500-word
          scouting summary covering strengths, weaknesses, playoff
          performance, and trends. Stored as a single chunk with{" "}
          <code>article_type = 'authored_summary'</code> and a higher
          retrieval prior so the synthesis layer gets a strong baseline
          on Tier-2 players.
        </p>
      </Step>
      <Step
        n={7}
        title="Query router"
        link={`${REPO_BLOB}/src/router/classifier.py`}
        linkLabel="router/classifier.py"
        heart
      >
        <p>
          The heart of the project. A Sonnet 4.5 classifier with few-shot
          examples reads the question and returns
          <code> {`{route, reasoning}`} </code>. <strong>stats</strong>{" "}
          → text-to-SQL on Postgres. <strong>prose</strong> → vector
          search with Cohere Rerank. <strong>hybrid</strong> → SQL filter
          to narrow the player set, then vector search inside that set.
          The reasoning string surfaces in the trace sidebar so the
          decision is auditable.
        </p>
        <p className="text-text-dim">
          A follow-up turn passes a short conversation history into the
          hybrid SQL prompt so pronouns like "him" can resolve against
          the previous answer.
        </p>
      </Step>
      <Step
        n={8}
        title="Synthesis with visible tool use"
        link={`${REPO_BLOB}/src/synthesize`}
        linkLabel="src/synthesize"
      >
        <p>
          Retrieved stats and chunks go to Claude Opus 4.6. The key UX
          move: the UI shows exactly what happened — the SQL that ran,
          the chunks that came back, the router's reasoning, and the
          model's cited paragraphs. Visible tool use is what makes the
          demo legible.
        </p>
      </Step>
      <Step
        n={9}
        title="Eval set with Braintrust"
        link={`${REPO_BLOB}/src/eval`}
        linkLabel="src/eval"
      >
        <p>
          30 test queries, stratified: 10 stats, 10 prose, 10 hybrid.
          Each case has an expected route, expected SQL or chunk ids,
          and a model-graded answer rubric. Router accuracy, SQL
          correctness, and retrieval recall are tracked separately so a
          regression in one path doesn't hide behind another's wins.
        </p>
      </Step>
      <Step
        n={10}
        title="The UI"
        link={`${REPO_BLOB}/ui`}
        linkLabel="ui/"
      >
        <p>
          Next.js 15 App Router, Tailwind, framer-motion, deployed
          locally for the demo. The visible-tool-use sidebar shows
          router decision, SQL panel, retrieved chunks, citations.
          A live RAG pipeline banner animates per stage on every turn,
          and copy buttons land question / answer / trace on the
          clipboard for follow-up workflows.
        </p>
      </Step>
    </ol>
  );
}

function Step({
  n,
  title,
  link,
  linkLabel,
  unsexy,
  heart,
  children,
}: {
  n: number;
  title: string;
  link: string;
  linkLabel: string;
  unsexy?: boolean;
  heart?: boolean;
  children: React.ReactNode;
}) {
  return (
    <li className="relative rounded-2xl border hairline bg-surface/40 p-5 backdrop-blur-md">
      <div className="mb-2 flex flex-wrap items-baseline gap-2">
        <span
          className="inline-flex h-6 w-6 items-center justify-center rounded-md border hairline-strong bg-bg-elev font-mono text-[11px]"
          aria-hidden="true"
        >
          {n}
        </span>
        <h3 className="text-[15.5px] font-semibold text-text">{title}</h3>
        {heart && (
          <span className="rounded-md border border-[rgba(255,106,31,0.45)] bg-[rgba(255,106,31,0.10)] px-1.5 py-0.5 text-[9.5px] uppercase tracking-[0.18em] text-[#ffb380]">
            the heart
          </span>
        )}
        {unsexy && (
          <span className="rounded-md border border-[rgba(251,191,36,0.40)] bg-[rgba(251,191,36,0.08)] px-1.5 py-0.5 text-[9.5px] uppercase tracking-[0.18em] text-[#fcd34d]">
            unsexy gold
          </span>
        )}
        <a
          href={link}
          target="_blank"
          rel="noreferrer"
          className="ml-auto inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[10.5px] text-text-dim transition-colors hover:bg-surface-2/60 hover:text-[#ffb380]"
        >
          <Code2 className="h-3 w-3" />
          {linkLabel} ↗
        </a>
      </div>
      <div className="space-y-2 text-[13.5px] leading-7 text-text-muted [&_code]:rounded-sm [&_code]:bg-surface-2/70 [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[12px] [&_code]:text-[#ffb380]">
        {children}
      </div>
    </li>
  );
}

function InterestingCallouts() {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <Callout
        title="Query routing as the heart"
        tone="ember"
        body="Most RAG demos handle one side of a split: structured numbers OR unstructured prose. The interesting move is letting the model decide which side each question belongs on — and then handling the questions that want both. The router's reasoning is surfaced in the trace so the decision is auditable."
      />
      <Callout
        title="Entity normalization, the unsexy gold"
        tone="amber"
        body="Every sports data team writes this code eventually. 1,525 aliases mapping 'the Chef' and 'Wardell' to 201939 means a player filter is a single integer match — pgvector's GIN index on player_ids[] turns 'guards praised for off-ball' into one fast query."
      />
      <Callout
        title="Visible tool use"
        tone="violet"
        body="The trace sidebar shows the SQL that ran, the chunks that came back, the router's reasoning, and the synthesis model's citations. That visibility is the difference between 'AI black box' and 'system you can debug'."
      />
      <Callout
        title="The conversation context fix"
        tone="rose"
        body="Follow-ups with pronouns ('compare him to...') used to fail because the SQL filter saw only the current question. Now the UI passes the last two completed turns as history, the model resolves the pronoun against the prior answer, and a fallback path runs unfiltered prose retrieval if the SQL still fails."
      />
    </div>
  );
}

function Callout({
  title,
  body,
  tone,
}: {
  title: string;
  body: string;
  tone: "ember" | "amber" | "violet" | "rose";
}) {
  const COLOR = {
    ember: "#ffb380",
    amber: "#fcd34d",
    violet: "#c4b5fd",
    rose: "#fda4af",
  } as const;
  const c = COLOR[tone];
  return (
    <div
      className="rounded-2xl border bg-surface/40 p-5 backdrop-blur-md"
      style={{ borderColor: `${c}55` }}
    >
      <h3
        className="mb-2 text-[12.5px] font-semibold uppercase tracking-[0.16em]"
        style={{ color: c }}
      >
        {title}
      </h3>
      <p className="text-[13px] leading-7 text-text-muted">{body}</p>
    </div>
  );
}

function TechStack() {
  return (
    <div className="rounded-2xl border hairline bg-surface/40 p-5 backdrop-blur-md md:p-6">
      <ul className="grid grid-cols-1 gap-3 text-[13px] md:grid-cols-2">
        <TechRow label="Python" value="3.11+ with uv for dependency management" />
        <TechRow label="Database" value="Postgres 16 + pgvector (local docker compose)" />
        <TechRow
          label="Stats"
          value="nba_api · basketball-reference scraping fallback"
        />
        <TechRow
          label="Prose"
          value="Reddit public .json + scraped articles · respect robots.txt"
        />
        <TechRow label="Embeddings" value="Voyage voyage-3-large (1024-dim)" />
        <TechRow label="Rerank" value="Cohere Rerank 3.5" />
        <TechRow
          label="Models"
          value="Sonnet 4.5 (router, text-to-SQL) · Opus 4.6 (synthesis) · Haiku 4.5 (pre-checks)"
        />
        <TechRow label="Backend" value="FastAPI · APScheduler · psycopg" />
        <TechRow label="Observability" value="Braintrust traces + eval" />
        <TechRow label="UI" value="Next.js 15 (App Router) · Tailwind · framer-motion" />
      </ul>
      <p className="mt-5 text-[12px] leading-6 text-text-dim">
        Note: <code className="rounded-sm bg-surface-2/70 px-1 py-0.5 font-mono text-[11px] text-[#ffb380]">docker-compose.yml</code>{" "}
        ships with <code className="rounded-sm bg-surface-2/70 px-1 py-0.5 font-mono text-[11px] text-[#ffb380]">POSTGRES_PASSWORD=nbarag</code>{" "}
        as a local-only dev placeholder that matches{" "}
        <code className="rounded-sm bg-surface-2/70 px-1 py-0.5 font-mono text-[11px] text-[#ffb380]">.env.example</code>. The container
        is bound to localhost and isn't exposed beyond the developer
        machine. Real credentials live in <code className="rounded-sm bg-surface-2/70 px-1 py-0.5 font-mono text-[11px] text-[#ffb380]">.env</code>,
        which is gitignored and never enters the repo.
      </p>
    </div>
  );
}

function TechRow({ label, value }: { label: string; value: string }) {
  return (
    <li className="flex items-baseline gap-3 rounded-md border hairline bg-surface-2/30 px-3 py-2">
      <span className="w-[100px] shrink-0 text-[10.5px] uppercase tracking-[0.18em] text-text-dim">
        {label}
      </span>
      <span className="text-[12.5px] text-text-muted">{value}</span>
    </li>
  );
}

function WhatsNext() {
  return (
    <div className="rounded-2xl border hairline bg-surface/40 p-5 backdrop-blur-md md:p-6">
      <ul className="space-y-3 text-[13.5px] leading-7 text-text-muted">
        <NextItem icon={Layers}>
          Expand the eval set to 100 cases across all three routes so the
          regression signal is stronger before each model upgrade.
        </NextItem>
        <NextItem icon={Wrench}>
          Add a "compare to last season" hybrid path so questions about
          year-over-year trends get a dedicated SQL template instead of
          a one-off prompt.
        </NextItem>
        <NextItem icon={Sparkles}>
          Stream the synthesis answer token-by-token in the UI instead of
          rendering it at the end so the pipeline banner and the
          response feel like one continuous animation.
        </NextItem>
      </ul>
      <a
        href={REPO_URL}
        target="_blank"
        rel="noreferrer"
        data-testid="build-footer-github-link"
        className="mt-6 inline-flex items-center gap-2 rounded-xl border border-[rgba(255,106,31,0.40)] bg-[rgba(255,106,31,0.08)] px-4 py-2.5 text-[12.5px] font-semibold uppercase tracking-[0.14em] text-[#ffb380] transition-colors hover:bg-[rgba(255,106,31,0.14)] hover:border-[rgba(255,106,31,0.65)]"
      >
        <Code2 className="h-4 w-4" />
        Read the code on GitHub
        <span>↗</span>
      </a>
    </div>
  );
}

function NextItem({
  icon: Icon,
  children,
}: {
  icon: typeof Layers;
  children: React.ReactNode;
}) {
  return (
    <li className="flex items-start gap-3">
      <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md border hairline bg-surface-2/40">
        <Icon className="h-3 w-3 text-text-muted" aria-hidden="true" />
      </span>
      <span>{children}</span>
    </li>
  );
}

// --- Tiny helpers -----------------------------------------------------------

function SectionDivider({ id, label }: { id: string; label: string }) {
  return (
    <div id={id} className="mt-12 mb-5 flex items-center gap-3">
      <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#ffb380]">
        {label}
      </span>
      <span className="h-px flex-1 bg-gradient-to-r from-[rgba(255,106,31,0.30)] via-white/8 to-transparent" />
    </div>
  );
}

function PageFooter() {
  return (
    <footer className="mt-16 border-t hairline pt-5 text-center text-[11px] uppercase tracking-[0.18em] text-text-dim">
      Ball Knowledge Oracle · 2025-26 · by Isaiah M.
    </footer>
  );
}
