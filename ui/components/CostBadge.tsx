interface Props {
  costUsd: number;
  elapsedMs: number;
  model?: string;
}

export function CostBadge({ costUsd, elapsedMs, model }: Props) {
  const dollars =
    costUsd >= 0.01 ? `$${costUsd.toFixed(3)}` : `$${costUsd.toFixed(5)}`;
  const seconds = (elapsedMs / 1000).toFixed(2);
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-700 ring-1 ring-inset ring-zinc-200 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-800">
      <span>{dollars}</span>
      <span className="text-zinc-400">·</span>
      <span>{seconds}s</span>
      {model && (
        <>
          <span className="text-zinc-400">·</span>
          <span className="font-mono text-[10px]">{model.split("-").slice(1, 3).join("-")}</span>
        </>
      )}
    </span>
  );
}
