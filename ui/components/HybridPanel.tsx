import type { HybridOut } from "@/lib/api";
import { RetrievalPanel } from "./RetrievalPanel";

interface Props {
  hybrid: HybridOut;
  citedChunkIds?: number[];
}

export function HybridPanel({ hybrid, citedChunkIds = [] }: Props) {
  const f = hybrid.filter;
  return (
    <div className="space-y-3">
      <section className="space-y-2">
        <h4 className="text-[10px] uppercase tracking-wide text-zinc-500">
          Numeric half · SQL
        </h4>
        <pre className="overflow-x-auto rounded-md bg-zinc-900 p-2 text-[11px] leading-5 text-zinc-100">
          <code>{f.sql}</code>
        </pre>
        {Object.keys(f.params).length > 0 && (
          <pre className="overflow-x-auto rounded-md bg-zinc-900 p-2 text-[11px] leading-5 text-zinc-100">
            <code>{JSON.stringify(f.params, null, 2)}</code>
          </pre>
        )}
        {f.rows.length > 0 && <ResultsTable rows={f.rows} cols={f.column_names} />}
        <div className="text-xs text-zinc-700 dark:text-zinc-300">
          {f.row_count} row{f.row_count === 1 ? "" : "s"}, narrowed prose to{" "}
          <span className="font-mono">{f.player_ids.length}</span> player
          {f.player_ids.length === 1 ? "" : "s"}.
        </div>
        {f.explanation && <div className="text-xs text-zinc-500">{f.explanation}</div>}
      </section>

      {hybrid.retrieval && (
        <section className="space-y-2 border-t border-zinc-200 pt-3 dark:border-zinc-800">
          <h4 className="text-[10px] uppercase tracking-wide text-zinc-500">
            Qualitative half · Prose (filtered to those players)
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

function ResultsTable({ rows, cols }: { rows: Record<string, unknown>[]; cols: string[] }) {
  const columns = cols.length > 0 ? cols : Object.keys(rows[0] ?? {});
  return (
    <div className="overflow-x-auto rounded-md border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-left text-[11px]">
        <thead className="bg-zinc-100 dark:bg-zinc-900">
          <tr>
            {columns.map((c) => (
              <th key={c} className="px-2 py-1.5 font-medium text-zinc-700 dark:text-zinc-300">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 25).map((row, i) => (
            <tr
              key={i}
              className="border-t border-zinc-100 odd:bg-white even:bg-zinc-50 dark:border-zinc-800 dark:odd:bg-zinc-900 dark:even:bg-zinc-950"
            >
              {columns.map((c) => (
                <td
                  key={c}
                  className="px-2 py-1 font-mono text-zinc-800 dark:text-zinc-200"
                >
                  {fmt(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") {
    return Number.isInteger(v) ? String(v) : v.toFixed(3);
  }
  return String(v);
}
