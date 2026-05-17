import { Fragment } from "react";
import type { CitationOut } from "@/lib/api";

interface Props {
  answer: string;
  citations: CitationOut[];
  declined?: boolean;
}

// Inline citation pattern Claude is instructed to emit, e.g. "...he scored [^3]"
const CITATION_RE = /\[\^(\d+)\]/g;

export function AnswerPanel({ answer, citations, declined }: Props) {
  const byIdx = new Map(citations.map((c) => [c.citation_index, c.chunk_id]));

  // Split the answer text into runs so each [^N] becomes a styled marker.
  // We keep this rendering deliberately simple — no markdown parser, just
  // citation substitution. Paragraphs are split on double newlines.
  return (
    <div className="space-y-3">
      {declined && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          The model declined to answer with the available context.
        </div>
      )}
      {answer.split(/\n{2,}/).map((para, pi) => (
        <p
          key={pi}
          className="whitespace-pre-wrap text-sm leading-6 text-zinc-800 dark:text-zinc-200"
        >
          {renderCitations(para, byIdx)}
        </p>
      ))}
    </div>
  );
}

function renderCitations(text: string, byIdx: Map<number, number>) {
  const parts: React.ReactNode[] = [];
  let lastEnd = 0;
  let match: RegExpExecArray | null;
  CITATION_RE.lastIndex = 0;
  while ((match = CITATION_RE.exec(text)) !== null) {
    if (match.index > lastEnd) parts.push(text.slice(lastEnd, match.index));
    const n = Number(match[1]);
    const chunkId = byIdx.get(n);
    parts.push(
      <Fragment key={`${match.index}-${n}`}>
        <a
          href={chunkId ? `#chunk-${chunkId}` : undefined}
          title={chunkId ? `chunk #${chunkId}` : "unknown chunk"}
          className="ml-0.5 inline-block rounded bg-zinc-200 px-1 text-[10px] font-mono text-zinc-700 align-super no-underline hover:bg-zinc-300 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
        >
          {n}
        </a>
      </Fragment>,
    );
    lastEnd = match.index + match[0].length;
  }
  if (lastEnd < text.length) parts.push(text.slice(lastEnd));
  return parts;
}
