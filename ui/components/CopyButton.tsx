"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/cn";

interface Props {
  /** Text written to the clipboard on click. */
  value: string;
  /** Visible label. Defaults to "Copy". */
  label?: string;
  /** Compact pill (h-6, 10px text) vs the default (h-7, 11px text). */
  compact?: boolean;
  /** Hide the label so only the icon shows. The label is still used as
   *  aria-label + tooltip. */
  iconOnly?: boolean;
  className?: string;
}

/**
 * CopyButton — one-click clipboard copy with a brief "Copied" check
 * confirmation. Calls stopPropagation so it works inside parents that
 * have their own click handler (e.g. the TurnCard outer button).
 */
export function CopyButton({
  value,
  label = "Copy",
  compact,
  iconOnly,
  className,
}: Props) {
  const [copied, setCopied] = useState(false);

  async function handleClick(e: React.MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard writes can fail in non-secure contexts; leave the button
      // visually unchanged so the user knows the action didn't land.
    }
  }

  const liveLabel = copied ? "Copied" : label;
  return (
    <button
      type="button"
      onClick={handleClick}
      aria-label={liveLabel}
      title={liveLabel}
      data-testid="copy-button"
      data-copied={copied}
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-md border hairline bg-surface-2/70 text-text-muted",
        "transition-colors hover:border-[rgba(255,106,31,0.4)] hover:text-[#ffb380]",
        "focus:outline-none focus-ember",
        compact ? "h-6 px-1.5 text-[10px]" : "h-7 px-2 text-[11px]",
        copied && "border-[rgba(110,231,183,0.45)] text-[#6ee7b7]",
        iconOnly && "px-1.5",
        className,
      )}
    >
      {copied ? (
        <Check className="h-3 w-3" aria-hidden="true" />
      ) : (
        <Copy className="h-3 w-3" aria-hidden="true" />
      )}
      {!iconOnly && <span>{liveLabel}</span>}
    </button>
  );
}
