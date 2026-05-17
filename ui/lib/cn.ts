// Conditional class joiner. Filters out falsy values so callers can write
// cn("base", condition && "active") without boolean leakage into the DOM.
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
