# Frontend Design — Aesthetic and Stack

This skill is the design north star for the UI. Claude Code consults it whenever it touches frontend code. The point is to keep the visual style coherent and to avoid the generic AI-product aesthetic.

## The stack (committed)

- **Framework:** Next.js 15 with the App Router.
- **CSS:** Tailwind CSS (mobile-first by default).
- **Components:** shadcn/ui v4 (copy-pasteable Radix + Tailwind primitives — you own the code).
- **Motion:** Framer Motion. Sprinkle, don't drench.
- **Charts:** Recharts for line, bar, radar. Visx + d3 for the shot heatmap and any custom visualization.
- **Icons:** Lucide React (ships with shadcn).
- **Fonts:** Geist Sans for UI and body. Söhne Mono (or JetBrains Mono as a free fallback) for stat readouts and SQL code blocks.

## What "great" looks like for this project

A recruiter scrolling on their phone gets the point in 30 seconds. They open the laptop, hit the demo URL, and the desktop layout makes them stop scrolling. The tool-use sidebar is the killer feature — they see the system think.

The aesthetic is sporty-precise: tight type, generous whitespace, one accent color used sparingly, fast quiet transitions. Not "AI-flashy." Not "designer-portfolio fancy." Production-app polished.

## Color tokens

- Background dark: `#0f0f10` (warm dark, not pure black).
- Background light: `#fafaf7` (off-white).
- Foreground dark on light: `#171717`.
- Foreground light on dark: `#f5f5f5`.
- Accent: one color used for the route badge, the active-chip state, and the focus ring. Pick once and stick to it. Suggestion: `#f97316` (the orange of basketball leather) at 60% saturation for dark mode, slightly deeper for light.
- Stat color scale (heatmap): a five-step ramp from cool blue (cold zone) to warm orange (hot zone). Use the d3-scale-chromatic `interpolateRdYlBu` reversed.

## Type scale (responsive)

```jsx
// hero
<h1 className="text-2xl md:text-4xl lg:text-5xl tracking-tight font-medium">

// section
<h2 className="text-xl md:text-2xl tracking-tight">

// body
<p className="text-sm md:text-base leading-relaxed">

// numbers (stats readouts)
<span className="font-mono tabular-nums">42.1</span>
```

Always use `tabular-nums` for any number that might appear next to another number. Without it, "42" and "11" don't line up.

## Motion rules

- **Never longer than 250ms.** Anything longer feels slow.
- **Spring, not ease.** Framer Motion's `spring` physics feel native; CSS `ease-out` feels generic.
- **Respect `prefers-reduced-motion`.** Wrap motion in a `useReducedMotion()` check; fall back to instant.
- **One motion per interaction.** Layering "fade in + slide up + scale" reads as fussy. Pick the most meaningful one.

```jsx
import { motion, useReducedMotion } from "framer-motion"

const reduce = useReducedMotion()
<motion.div
  initial={reduce ? false : { opacity: 0, y: 8 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ type: "spring", stiffness: 350, damping: 30 }}
/>
```

## Project-specific component patterns

### Citation chip

Inline chip on every cited claim. Shows source name + date. Hover reveals the full source quote (shadcn `HoverCard`).

```jsx
<HoverCard>
  <HoverCardTrigger asChild>
    <span className="inline-flex items-center gap-1 rounded-md border bg-muted/40 px-1.5 py-0.5 text-xs">
      <Newspaper className="size-3" />
      The Athletic · Apr 12
    </span>
  </HoverCardTrigger>
  <HoverCardContent className="max-w-md text-sm">
    {quote}
  </HoverCardContent>
</HoverCard>
```

### Route badge (STATS / PROSE / HYBRID)

Lives in the tool-use sidebar. Color depends on route. Animate the appearance when the router decides.

### Tool-use sidebar (the demo killer)

Three-pane layout on desktop: chat in the center, sidebar on the right showing the route badge, the SQL panel (collapsed by default), the article cards. On mobile this collapses behind a "View tool use" button that opens a sheet.

```jsx
<div className="flex flex-col lg:flex-row gap-4">
  <main className="lg:w-2/3">{/* chat */}</main>
  <aside className="hidden lg:block lg:w-1/3">{/* sidebar */}</aside>
  <Sheet>{/* mobile drawer triggered by a button visible only below lg */}</Sheet>
</div>
```

### Court heatmap (Visx hexbin)

Half-court SVG underlay, hexbin density layer over it. Uses Visx's `Hexbin` from `@visx/hexbin`. Bin radius around 1.5 ft on a 50-ft-wide court SVG.

### Radar chart (player comparison)

Recharts `RadarChart` with 6 axes: TS%, USG%, AST%, DRB%, ORTG, DRTG. 2-3 players overlaid. Use the accent color for player 1; muted variants for 2 and 3.

### Empty states

Specific copy. Never "No data."

- Chat empty: "Ask anything about the 2025-26 season. Try: *Which guards shooting above 40% from three are getting praised for off-ball movement?*"
- Search empty: "I couldn't find that. Try widening the date range or checking the player name."

### Loading states

Specific. "Querying 1,247 chunks…" beats a spinner alone. "Asking the router…" beats "Loading…"

## Anti-patterns

- **Pure black backgrounds.** Use `#0f0f10`. Pure black bleeds into device bezels and looks dead.
- **Five colors of equal weight.** Pick one accent. Everything else is neutral.
- **Bouncy spring physics on every interaction.** Reads as toy. Save the bounce for one or two delightful moments.
- **Animating longer than 250ms.** Slow.
- **`text-justify` on any body text.** River-of-rivers effect. Use `text-left`.
- **Inter for body text.** Overused. Geist Sans is a better default in 2026.
- **Square cards with no hover state.** Add at least a `hover:bg-muted/60` so things feel alive.
- **Skipping `useReducedMotion`.** Accessibility regression.

## When to reach for the shadcn MCP server

When implementing a new component, run the shadcn MCP server's `list` / `search` first. It exposes shadcn/ui v4 components by natural-language prompt ("install Avatar", "show me radar chart blocks", "find dashboard layouts"). Beats copy-pasting from web docs.

Set `GITHUB_PERSONAL_ACCESS_TOKEN` to lift the rate limit from 60/hour to 5000/hour. No scopes required.

## The interview line

"I used Next.js with shadcn/ui and Tailwind because that is the modern AI-product default and lets me focus engineering effort on the interesting parts — the tool-use sidebar, the shot-location heatmap, the visible router decisions. The boring foundation frees up budget for the parts that demonstrate the actual work."
