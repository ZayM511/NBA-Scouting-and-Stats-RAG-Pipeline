"use client";

import { useEffect, useRef } from "react";

/**
 * GalaxyBackground — performant animated starfield with a soft nebula glow.
 *
 * Strategy:
 *   • A handful of CSS gradients form the deep-space + nebula color base.
 *     They are GPU-composited, basically free.
 *   • A small <canvas> overlay paints ~180 stars that twinkle and drift
 *     slowly with parallax. The whole thing runs in a single
 *     requestAnimationFrame loop with cheap math (no per-pixel shaders).
 *   • DPR is capped at 1.5 so high-res displays don't blow up paint cost.
 *   • The loop pauses whenever the document is hidden, when the user has
 *     `prefers-reduced-motion`, or when the element scrolls off-screen
 *     (via IntersectionObserver).
 *
 * The whole bundle ships in under ~3 KB gzipped and adds no synchronous
 * work to first paint.
 */
interface Props {
  density?: number;   // stars per 100k px²
  className?: string;
}

interface Star {
  x: number;
  y: number;
  z: number;          // depth 0..1; smaller = farther
  r: number;          // radius
  twinklePhase: number;
  twinkleSpeed: number;
  driftX: number;     // pixels per second of parallax
  driftY: number;
  hue: number;        // tiny color variation
}

export function GalaxyBackground({ density = 0.6, className }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    let stars: Star[] = [];
    let width = 0;
    let height = 0;
    let dpr = 1;
    let lastT = performance.now();
    let visible = true;
    let intersecting = true;
    let stopped = false;

    const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");

    function makeStars() {
      const area = width * height;
      const count = Math.min(
        320,
        Math.max(60, Math.round((area / 100_000) * density * 30)),
      );
      stars = new Array(count).fill(0).map(() => {
        const z = Math.random() * 0.85 + 0.15;
        return {
          x: Math.random() * width,
          y: Math.random() * height,
          z,
          r: 0.4 + z * 1.7,
          twinklePhase: Math.random() * Math.PI * 2,
          twinkleSpeed: 0.4 + Math.random() * 1.2,
          driftX: (Math.random() - 0.5) * 6 * z,
          driftY: (Math.random() - 0.5) * 6 * z,
          hue: 200 + Math.random() * 60, // pale blue → faint purple
        };
      });
    }

    function resize() {
      const rect = canvas!.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas!.width = Math.round(width * dpr);
      canvas!.height = Math.round(height * dpr);
      ctx!.setTransform(1, 0, 0, 1, 0, 0);
      ctx!.scale(dpr, dpr);
      makeStars();
    }

    function frame(t: number) {
      if (stopped) return;
      const dt = Math.min(0.08, (t - lastT) / 1000); // clamp big tab-switch deltas
      lastT = t;

      const paused = !visible || !intersecting || reducedMotion.matches;
      if (!paused) {
        ctx!.clearRect(0, 0, width, height);
        for (const s of stars) {
          s.x += s.driftX * dt;
          s.y += s.driftY * dt;
          // Wrap
          if (s.x < -2) s.x = width + 2;
          if (s.x > width + 2) s.x = -2;
          if (s.y < -2) s.y = height + 2;
          if (s.y > height + 2) s.y = -2;

          s.twinklePhase += s.twinkleSpeed * dt;
          const tw = 0.55 + 0.45 * Math.sin(s.twinklePhase);
          const alpha = (0.35 + 0.55 * s.z) * tw;

          ctx!.beginPath();
          ctx!.fillStyle = `hsla(${s.hue}, 80%, 92%, ${alpha.toFixed(3)})`;
          ctx!.arc(s.x, s.y, s.r, 0, Math.PI * 2);
          ctx!.fill();
          // Bright stars get a soft glow
          if (s.r > 1.4) {
            ctx!.beginPath();
            ctx!.fillStyle = `hsla(${s.hue}, 90%, 90%, ${(alpha * 0.18).toFixed(3)})`;
            ctx!.arc(s.x, s.y, s.r * 3.2, 0, Math.PI * 2);
            ctx!.fill();
          }
        }
      }

      rafRef.current = requestAnimationFrame(frame);
    }

    const onVis = () => {
      visible = !document.hidden;
      lastT = performance.now();
    };
    const onResize = () => resize();
    const io = new IntersectionObserver(
      ([entry]) => {
        intersecting = entry.isIntersecting;
      },
      { rootMargin: "100px" },
    );

    resize();
    io.observe(canvas);
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("resize", onResize);
    lastT = performance.now();
    rafRef.current = requestAnimationFrame(frame);

    return () => {
      stopped = true;
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      io.disconnect();
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("resize", onResize);
    };
  }, [density]);

  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute inset-0 overflow-hidden ${className ?? ""}`}
    >
      {/* Deep space base + colored nebula glows. Pure CSS, no JS cost. */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 18% 12%, rgba(70,30,120,0.25) 0%, transparent 55%)," +
            "radial-gradient(ellipse 60% 55% at 82% 22%, rgba(20,80,150,0.20) 0%, transparent 60%)," +
            "radial-gradient(ellipse 90% 70% at 50% 100%, rgba(255,106,31,0.10) 0%, transparent 65%)," +
            "linear-gradient(180deg, #04040b 0%, #07070d 60%, #050509 100%)",
        }}
      />
      {/* Subtle drifting nebula veil — single GPU-composited transform. */}
      <div
        className="absolute inset-0 opacity-70 mix-blend-screen galaxy-drift"
        style={{
          background:
            "radial-gradient(ellipse 45% 35% at 60% 40%, rgba(180,120,255,0.10) 0%, transparent 70%)," +
            "radial-gradient(ellipse 38% 30% at 30% 70%, rgba(80,160,255,0.08) 0%, transparent 70%)",
        }}
      />
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
      <style>{`
        @keyframes galaxy-drift {
          0%   { transform: translate3d(0, 0, 0)   scale(1); }
          50%  { transform: translate3d(-12px, 8px, 0) scale(1.02); }
          100% { transform: translate3d(0, 0, 0)   scale(1); }
        }
        .galaxy-drift { animation: galaxy-drift 28s ease-in-out infinite; will-change: transform; }
        @media (prefers-reduced-motion: reduce) {
          .galaxy-drift { animation: none; }
        }
      `}</style>
    </div>
  );
}
