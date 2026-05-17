import { Coins, Timer } from "lucide-react";

interface Props {
  costUsd: number;
  elapsedMs: number;
  model?: string;
}

export function CostBadge({ costUsd, elapsedMs, model }: Props) {
  const dollars =
    costUsd >= 0.01 ? `$${costUsd.toFixed(3)}` : `$${costUsd.toFixed(5)}`;
  const seconds = (elapsedMs / 1000).toFixed(2);
  const shortModel = model ? model.split("-").slice(1, 3).join("-") : null;
  return (
    <span className="inline-flex items-center gap-2 rounded-md border hairline bg-surface-2/70 px-2 py-0.5 text-[10px] font-mono text-text-muted">
      <span className="inline-flex items-center gap-1">
        <Coins className="h-3 w-3" style={{ color: "#ffb380" }} />
        {dollars}
      </span>
      <span className="text-text-dim">·</span>
      <span className="inline-flex items-center gap-1">
        <Timer className="h-3 w-3" />
        {seconds}s
      </span>
      {shortModel && (
        <>
          <span className="text-text-dim">·</span>
          <span>{shortModel}</span>
        </>
      )}
    </span>
  );
}
