import { AlertOctagon, Hash } from "lucide-react";
import { cn } from "@/lib/cn";
import type { StatsOut } from "@/lib/api";

interface Props {
  stats: StatsOut;
}

export function StatsPanel({ stats }: Props) {
  return (
    <div className="space-y-3">
      {stats.status !== "ok" && (
        <div className="flex items-start gap-2 rounded-xl border border-[rgba(251,113,133,0.30)] bg-[rgba(251,113,133,0.06)] px-3 py-2 text-xs text-[#fda4af]">
          <AlertOctagon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <div className="space-y-1">
            <div>Status: {stats.status}</div>
            {stats.error && <div className="font-mono opacity-90">{stats.error}</div>}
          </div>
        </div>
      )}

      {stats.sql && <CodeBlock label="SQL" value={stats.sql} lang="sql" />}

      {stats.params && Object.keys(stats.params).length > 0 && (
        <CodeBlock label="Params" value={JSON.stringify(stats.params, null, 2)} lang="json" />
      )}

      {stats.explanation && (
        <div className="rounded-xl border hairline bg-surface-2/60 p-2.5">
          <div className="mb-1 text-[9px] uppercase tracking-[0.18em] text-text-dim">
            Explanation
          </div>
          <p className="text-xs leading-5 text-text-muted">{stats.explanation}</p>
        </div>
      )}

      {stats.rows && stats.rows.length > 0 && <ResultsTable rows={stats.rows} />}

      <div className="flex flex-wrap items-center gap-2 text-[10px] font-mono text-text-dim">
        {stats.row_count !== null && (
          <span className="inline-flex items-center gap-1 rounded-md border hairline px-1.5 py-0.5">
            <Hash className="h-2.5 w-2.5" />
            {stats.row_count} rows
          </span>
        )}
        {stats.elapsed_ms !== null && (
          <span className="inline-flex items-center gap-1 rounded-md border hairline px-1.5 py-0.5">
            {stats.elapsed_ms.toFixed(0)}ms exec
          </span>
        )}
      </div>
    </div>
  );
}

function CodeBlock({
  label,
  value,
  lang,
}: {
  label: string;
  value: string;
  lang?: string;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center gap-2">
        <span className="text-[9px] uppercase tracking-[0.18em] text-text-dim">
          {label}
        </span>
        {lang && (
          <span className="rounded border hairline px-1 py-px text-[9px] font-mono text-text-dim">
            {lang}
          </span>
        )}
      </div>
      <pre className="overflow-x-auto rounded-xl border hairline bg-[#08080c] p-3 text-[11.5px] leading-5 text-[#e4e4e7] font-mono">
        <code>{value}</code>
      </pre>
    </div>
  );
}

function ResultsTable({ rows }: { rows: Record<string, unknown>[] }) {
  const cols = Object.keys(rows[0] ?? {});
  return (
    <div>
      <div className="mb-1 text-[9px] uppercase tracking-[0.18em] text-text-dim">
        Results
      </div>
      <div className="overflow-x-auto rounded-xl border hairline bg-surface-2/60">
        <table className="w-full text-left text-[11.5px]">
          <thead className="border-b hairline bg-surface-3/60">
            <tr>
              {cols.map((c) => (
                <th
                  key={c}
                  className="px-2.5 py-2 font-medium uppercase tracking-wider text-[10px] text-text-muted"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 50).map((row, i) => (
              <tr
                key={i}
                className={cn(
                  "border-t hairline transition-colors hover:bg-[rgba(255,255,255,0.03)]",
                  i % 2 === 1 && "bg-[rgba(255,255,255,0.015)]",
                )}
              >
                {cols.map((c) => (
                  <td key={c} className="px-2.5 py-1.5 font-mono text-text">
                    {fmt(row[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > 50 && (
        <div className="mt-1 text-[10px] text-text-dim">
          showing first 50 of {rows.length}
        </div>
      )}
    </div>
  );
}

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(3);
  return String(v);
}
