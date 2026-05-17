import type { StatsOut } from "@/lib/api";

interface Props {
  stats: StatsOut;
}

export function StatsPanel({ stats }: Props) {
  return (
    <div className="space-y-3">
      {stats.status !== "ok" && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-900 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          Status: {stats.status}
          {stats.error && <div className="mt-1 font-mono">{stats.error}</div>}
        </div>
      )}

      {stats.sql && (
        <CodeBlock label="SQL" value={stats.sql} />
      )}

      {stats.params && Object.keys(stats.params).length > 0 && (
        <CodeBlock label="Params" value={JSON.stringify(stats.params, null, 2)} />
      )}

      {stats.explanation && (
        <div className="rounded-md bg-zinc-50 p-2 text-xs text-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-zinc-500">
            Explanation
          </div>
          {stats.explanation}
        </div>
      )}

      {stats.rows && stats.rows.length > 0 && <ResultsTable rows={stats.rows} />}

      <div className="flex flex-wrap gap-2 text-[10px] text-zinc-500">
        {stats.row_count !== null && <span>{stats.row_count} rows</span>}
        {stats.elapsed_ms !== null && <span>{stats.elapsed_ms.toFixed(0)}ms exec</span>}
      </div>
    </div>
  );
}

function CodeBlock({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="mb-1 text-[10px] uppercase tracking-wide text-zinc-500">{label}</div>
      <pre className="overflow-x-auto rounded-md bg-zinc-900 p-2 text-[11px] leading-5 text-zinc-100">
        <code>{value}</code>
      </pre>
    </div>
  );
}

function ResultsTable({ rows }: { rows: Record<string, unknown>[] }) {
  const cols = Object.keys(rows[0] ?? {});
  return (
    <div>
      <div className="mb-1 text-[10px] uppercase tracking-wide text-zinc-500">Results</div>
      <div className="overflow-x-auto rounded-md border border-zinc-200 dark:border-zinc-800">
        <table className="w-full text-left text-[11px]">
          <thead className="bg-zinc-100 dark:bg-zinc-900">
            <tr>
              {cols.map((c) => (
                <th key={c} className="px-2 py-1.5 font-medium text-zinc-700 dark:text-zinc-300">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 50).map((row, i) => (
              <tr
                key={i}
                className="border-t border-zinc-100 odd:bg-white even:bg-zinc-50 dark:border-zinc-800 dark:odd:bg-zinc-900 dark:even:bg-zinc-950"
              >
                {cols.map((c) => (
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
      {rows.length > 50 && (
        <div className="mt-1 text-[10px] text-zinc-500">
          showing first 50 of {rows.length}
        </div>
      )}
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
