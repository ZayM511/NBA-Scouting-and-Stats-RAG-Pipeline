import { Fragment } from "react";
import { Sparkles } from "lucide-react";
import type { CitationOut } from "@/lib/api";
import { CopyButton } from "./CopyButton";

interface Props {
  answer: string;
  citations: CitationOut[];
  declined?: boolean;
}

const CITATION_RE = /\[\^(\d+)\]/g;

export function AnswerPanel({ answer, citations, declined }: Props) {
  const byIdx = new Map(citations.map((c) => [c.citation_index, c.chunk_id]));

  return (
    <div className="space-y-3">
      {declined && (
        <div className="flex items-start gap-2 rounded-xl border border-[rgba(251,191,36,0.25)] bg-[rgba(251,191,36,0.06)] px-3 py-2 text-sm text-[#fcd34d]">
          <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          The model declined to answer with the available context.
        </div>
      )}
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
          Answer
        </span>
        <CopyButton value={answer} label="Copy answer" compact />
      </div>
      <div className="space-y-3">
        {answer.split(/\n{2,}/).map((para, pi) => (
          <p
            key={pi}
            className="whitespace-pre-wrap text-[14.5px] leading-7 text-text"
          >
            {renderCitations(para, byIdx)}
          </p>
        ))}
      </div>
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
          onClick={(e) => {
            e.stopPropagation();
            if (chunkId) {
              document
                .getElementById(`chunk-${chunkId}`)
                ?.scrollIntoView({ behavior: "smooth", block: "center" });
            }
          }}
          className="ml-0.5 inline-flex h-4 min-w-[16px] items-center justify-center rounded-[5px] px-1 align-super text-[10px] font-mono font-medium no-underline transition-colors"
          style={{
            background: "rgba(255,106,31,0.14)",
            color: "#ffb380",
            boxShadow: "inset 0 0 0 1px rgba(255,106,31,0.35)",
          }}
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
