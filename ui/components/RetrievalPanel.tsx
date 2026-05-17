import type { RetrievalOut } from "@/lib/api";

interface Props {
  retrieval: RetrievalOut;
  citedChunkIds?: number[];
}

export function RetrievalPanel({ retrieval, citedChunkIds = [] }: Props) {
  const cited = new Set(citedChunkIds);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2 text-xs">
        <Stat label="BM25" value={retrieval.bm25_count} />
        <Stat label="Dense" value={retrieval.dense_count} />
        <Stat label="Merged" value={retrieval.merged_count} />
      </div>
      <div className="space-y-2">
        {retrieval.chunks.map((c, i) => {
          const isCited = cited.has(c.chunk_id);
          return (
            <div
              key={c.chunk_id}
              id={`chunk-${c.chunk_id}`}
              className={
                "rounded-md border p-2 text-xs " +
                (isCited
                  ? "border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/40"
                  : "border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900")
              }
            >
              <div className="mb-1 flex items-center justify-between gap-2 text-[10px] uppercase tracking-wide text-zinc-500">
                <span className="font-mono">
                  #{i + 1} · chunk {c.chunk_id} · {c.source}
                </span>
                <span className="font-mono">{c.score.toFixed(3)}</span>
              </div>
              <p className="line-clamp-4 text-zinc-700 dark:text-zinc-300">{c.text}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-zinc-100 p-2 text-center dark:bg-zinc-900">
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="font-mono text-sm text-zinc-900 dark:text-zinc-100">{value}</div>
    </div>
  );
}
