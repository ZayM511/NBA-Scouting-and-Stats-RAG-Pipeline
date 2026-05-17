import { cn } from "@/lib/cn";
import type { RouteName } from "@/lib/api";

const STYLES: Record<RouteName, string> = {
  prose: "bg-blue-100 text-blue-900 ring-blue-200 dark:bg-blue-950 dark:text-blue-200 dark:ring-blue-900",
  stats: "bg-emerald-100 text-emerald-900 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-200 dark:ring-emerald-900",
  hybrid: "bg-violet-100 text-violet-900 ring-violet-200 dark:bg-violet-950 dark:text-violet-200 dark:ring-violet-900",
};

interface Props {
  route: RouteName;
  reasoning?: string;
}

export function RouteBadge({ route, reasoning }: Props) {
  return (
    <span
      title={reasoning ?? undefined}
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        STYLES[route],
      )}
    >
      {route}
    </span>
  );
}
