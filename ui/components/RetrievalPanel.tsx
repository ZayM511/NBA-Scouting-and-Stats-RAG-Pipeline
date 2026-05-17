import type { RetrievalOut } from "@/lib/api";
import { cn } from "@/lib/cn";

interface Props {
  retrieval: RetrievalOut;
  citedChunkIds?: number[];
}

export function RetrievalPanel({ retrieval, citedChunkIds = [] }: Props) {
  const cited = new Set(citedChunkIds);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        <Stat label="BM25" value={retrieval.bm25_count} />
        <Stat label="Dense" value={retrieval.dense_count} />
        <Stat label="Merged" value={retrieval.merged_count} accent />
      </div>
      <div className="space-y-2">
        {retrieval.chunks.map((c, i) => {
          const isCited = cited.has(c.chunk_id);
          return (
            <div
              key={c.chunk_id}
              id={`chunk-${c.chunk_id}`}
              className={cn(
                "rounded-xl border p-2.5 text-xs transition-colors",
                isCited
                  ? "border-[rgba(255,106,31,0.40)] bg-[rgba(255,106,31,0.06)]"
                  : "hairline bg-surface-2/60 hover:bg-surface-2",
              )}
            >
              <div className="mb-1.5 flex items-center justify-between gap-2 text-[10px] uppercase tracking-wider">
                <span className="font-mono text-text-dim">
                  #{i + 1} · chunk {c.chunk_id} ·{" "}
                  <span className="text-text-muted">{c.source}</span>
                </span>
                <span
                  className="rounded-md px-1.5 py-0.5 font-mono"
                  style={{
                    background: isCited
                      ? "rgba(255,106,31,0.15)"
                      : "rgba(255,255,255,0.05)",
                    color: isCited ? "#ffb380" : "#a1a1aa",
                  }}
                >
                  {c.score.toFixed(3)}
                </span>
              </div>
              <p className="line-clamp-4 text-[12.5px] leading-5 text-text-muted">
                {c.text}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border p-2 text-center",
        accent
          ? "border-[rgba(255,106,31,0.30)] bg-[rgba(255,106,31,0.06)]"
          : "hairline bg-surface-2/60",
      )}
    >
      <div className="text-[9px] uppercase tracking-[0.16em] text-text-dim">
        {label}
      </div>
      <div
        className={cn(
          "mt-0.5 font-mono text-sm",
          accent ? "text-[#ffb380]" : "text-text",
        )}
      >
        {value}
      </div>
    </div>
  );
}
