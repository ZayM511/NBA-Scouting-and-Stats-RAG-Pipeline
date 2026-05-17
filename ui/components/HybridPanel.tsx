import { Filter, Search } from "lucide-react";
import { cn } from "@/lib/cn";
import type { HybridOut } from "@/lib/api";
import { RetrievalPanel } from "./RetrievalPanel";

interface Props {
  hybrid: HybridOut;
  citedChunkIds?: number[];
}

export function HybridPanel({ hybrid, citedChunkIds = [] }: Props) {
  const f = hybrid.filter;
  // Defensive defaults: older API responses cached in client state may not
  // include rows / column_names / row_count (those landed in Phase L.4).
  const rows = f.rows ?? [];
  const cols = f.column_names ?? [];
  const rowCount = f.row_count ?? rows.length;
  const playerIds = f.player_ids ?? [];
  const params = f.params ?? {};

  return (
    <div className="space-y-4">
      <section className="space-y-2">
        <StepHeader index={1} icon={<Filter className="h-3 w-3" />} title="Numeric half · SQL" />
        <pre className="overflow-x-auto rounded-xl border hairline bg-[#08080c] p-3 text-[11.5px] leading-5 text-[#e4e4e7] font-mono">
          <code>{f.sql}</code>
        </pre>
        {Object.keys(params).length > 0 && (
          <pre className="overflow-x-auto rounded-xl border hairline bg-[#08080c] p-3 text-[11.5px] leading-5 text-[#e4e4e7] font-mono">
            <code>{JSON.stringify(params, null, 2)}</code>
          </pre>
        )}
        {rows.length > 0 && <ResultsTable rows={rows} cols={cols} />}
        <div className="rounded-xl border hairline bg-surface-2/60 px-3 py-2 text-xs text-text-muted">
          <span className="font-mono text-[#ffb380]">{rowCount}</span>{" "}
          row{rowCount === 1 ? "" : "s"}, narrowed prose to{" "}
          <span className="font-mono text-[#ffb380]">{playerIds.length}</span> player
          {playerIds.length === 1 ? "" : "s"}.
          {f.explanation && (
            <div className="mt-1.5 text-text-dim">{f.explanation}</div>
          )}
        </div>
      </section>

      {hybrid.retrieval && (
        <section className="space-y-2 border-t hairline pt-3">
          <StepHeader
            index={2}
            icon={<Search className="h-3 w-3" />}
            title="Qualitative half · Prose (filtered to those players)"
          />
          <RetrievalPanel retrieval={hybrid.retrieval} citedChunkIds={citedChunkIds} />
        </section>
      )}

      {hybrid.notes && (
        <div className="rounded-xl border border-[rgba(251,191,36,0.25)] bg-[rgba(251,191,36,0.06)] px-3 py-2 text-xs text-[#fcd34d]">
          {hybrid.notes}
        </div>
      )}
    </div>
  );
}

function StepHeader({
  index,
  icon,
  title,
}: {
  index: number;
  icon: React.ReactNode;
  title: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span
        className="inline-flex h-5 w-5 items-center justify-center rounded-md text-[10px] font-mono font-semibold"
        style={{
          background: "rgba(167,139,250,0.14)",
          color: "#c4b5fd",
          boxShadow: "inset 0 0 0 1px rgba(167,139,250,0.30)",
        }}
      >
        {index}
      </span>
      <span className="text-[10px] uppercase tracking-[0.18em] text-text-muted inline-flex items-center gap-1.5">
        {icon} {title}
      </span>
    </div>
  );
}

function ResultsTable({
  rows,
  cols,
}: {
  rows: Record<string, unknown>[];
  cols: string[];
}) {
  const columns = cols.length > 0 ? cols : Object.keys(rows[0] ?? {});
  return (
    <div className="overflow-x-auto rounded-xl border hairline bg-surface-2/60">
      <table className="w-full text-left text-[11.5px]">
        <thead className="border-b hairline bg-surface-3/60">
          <tr>
            {columns.map((c) => (
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
          {rows.slice(0, 25).map((row, i) => (
            <tr
              key={i}
              className={cn(
                "border-t hairline transition-colors hover:bg-[rgba(255,255,255,0.03)]",
                i % 2 === 1 && "bg-[rgba(255,255,255,0.015)]",
              )}
            >
              {columns.map((c) => (
                <td key={c} className="px-2.5 py-1.5 font-mono text-text">
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
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(3);
  return String(v);
}
