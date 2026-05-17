import { BarChart3, Brain, Layers, Sparkles } from "lucide-react";
import { cn } from "@/lib/cn";
import type { RouteName } from "@/lib/api";

const ROUTE_META: Record<RouteName, {
  icon: typeof BarChart3;
  color: string;
  bg: string;
  ring: string;
}> = {
  stats: {
    icon: BarChart3,
    color: "#6ee7b7",
    bg: "rgba(52,211,153,0.10)",
    ring: "rgba(52,211,153,0.35)",
  },
  prose: {
    icon: Brain,
    color: "#7dd3fc",
    bg: "rgba(125,211,252,0.10)",
    ring: "rgba(125,211,252,0.35)",
  },
  hybrid: {
    icon: Layers,
    color: "#c4b5fd",
    bg: "rgba(167,139,250,0.12)",
    ring: "rgba(167,139,250,0.40)",
  },
  oracle: {
    icon: Sparkles,
    color: "#ffb380",
    bg: "rgba(255,106,31,0.12)",
    ring: "rgba(255,106,31,0.40)",
  },
};

interface Props {
  route: RouteName;
  reasoning?: string;
  size?: "sm" | "md";
}

export function RouteBadge({ route, reasoning, size = "sm" }: Props) {
  const m = ROUTE_META[route];
  const Icon = m.icon;
  return (
    <span
      title={reasoning ?? undefined}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md font-medium uppercase tracking-wider",
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]",
      )}
      style={{
        color: m.color,
        background: m.bg,
        boxShadow: `inset 0 0 0 1px ${m.ring}`,
      }}
    >
      <Icon className={size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} />
      {route}
    </span>
  );
}
