import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// shadcn-style class merger: clsx handles conditional classes,
// twMerge dedupes conflicting Tailwind utilities so callers can pass overrides.
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
