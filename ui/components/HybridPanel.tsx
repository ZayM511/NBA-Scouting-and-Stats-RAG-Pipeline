import type { HybridOut } from "@/lib/api";
import { RetrievalPanel } from "./RetrievalPanel";

interface Props {
  hybrid: HybridOut;
  citedChunkIds?: number[];
}

export function HybridPanel({ hybrid, citedChunkIds = [] }: Props) {
  return (
    <div className="space-y-3">
      <section className="space-y-2">
        <h4 className="text-[10px] uppercase tracking-wide text-zinc-500">
          Step 1 · SQL filter
        </h4>
        <pre className="overflow-x-auto rounded-md bg-zinc-900 p-2 text-[11px] leading-5 text-zinc-100">
          <code>{hybrid.filter.sql}</code>
        </pre>
        {Object.keys(hybrid.filter.params).length > 0 && (
          <pre className="overflow-x-auto rounded-md bg-zinc-900 p-2 text-[11px] leading-5 text-zinc-100">
            <code>{JSON.stringify(hybrid.filter.params, null, 2)}</code>
          </pre>
        )}
        <div className="text-xs text-zinc-700 dark:text-zinc-300">
          Narrowed to <span className="font-mono">{hybrid.filter.player_ids.length}</span>{" "}
          player(s):{" "}
          <span className="font-mono text-[11px]">
            {hybrid.filter.player_ids.slice(0, 10).join(", ")}
            {hybrid.filter.player_ids.length > 10 && " …"}
          </span>
        </div>
        {hybrid.filter.explanation && (
          <div className="text-xs text-zinc-500">{hybrid.filter.explanation}</div>
        )}
      </section>

      {hybrid.retrieval && (
        <section className="space-y-2 border-t border-zinc-200 pt-3 dark:border-zinc-800">
          <h4 className="text-[10px] uppercase tracking-wide text-zinc-500">
            Step 2 · Prose retrieval (filtered)
          </h4>
          <RetrievalPanel retrieval={hybrid.retrieval} citedChunkIds={citedChunkIds} />
        </section>
      )}

      {hybrid.notes && (
        <div className="rounded-md bg-amber-50 px-2 py-1.5 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          {hybrid.notes}
        </div>
      )}
    </div>
  );
}
