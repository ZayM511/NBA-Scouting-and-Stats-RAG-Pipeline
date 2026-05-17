"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, SkipForward, Volume2, VolumeX } from "lucide-react";

/**
 * IntroVideo — full-screen cinematic intro that plays on every page load.
 *
 * Snappy loading strategy:
 *   • Source MP4 has its moov atom at the front (re-encoded with
 *     ffmpeg -movflags +faststart) so the browser begins playback after
 *     a fraction of the file has arrived rather than waiting for the
 *     whole download.
 *   • `preload="auto"` — start fetching immediately on mount.
 *   • `poster` — JPEG of the first frame is shown instantly while the
 *     video element downloads / decodes, so there is never a black
 *     screen.
 *   • The waiting/stalled events flip a `buffering` flag that surfaces
 *     a soft loader, so any mid-stream pause is visibly intentional
 *     instead of a freeze.
 *
 * Controls:
 *   • Unmute / mute (volume icon — pulsing ring while muted)
 *   • Skip (top-right + the ESC key)
 *
 * Dismisses on skip, on video end, on ESC, or after a hard timeout (so a
 * missing asset never traps the user).
 */

interface Props {
  src?: string;
  poster?: string;
  /** Auto-skip the overlay after N seconds even if the video never loads. */
  hardTimeoutSec?: number;
}

export function IntroVideo({
  src = "/intro.mp4",
  poster = "/intro-poster.jpg",
  hardTimeoutSec = 22,
}: Props) {
  const [open, setOpen] = useState(true);
  const [muted, setMuted] = useState(true);
  const [ready, setReady] = useState(false);
  const [buffering, setBuffering] = useState(true);
  const [progress, setProgress] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Sync muted state with the element. On unmute, ensure we resume play.
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    v.muted = muted;
    if (!muted && v.paused) {
      v.play().catch(() => setMuted(true));
    }
  }, [muted]);

  // ESC dismisses.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Hard timeout if the video never reports `canplay`.
  useEffect(() => {
    if (ready) return;
    const t = setTimeout(() => setOpen(false), hardTimeoutSec * 1000);
    return () => clearTimeout(t);
  }, [ready, hardTimeoutSec]);

  function skip() {
    setOpen(false);
  }

  function toggleMute() {
    setMuted((m) => !m);
  }

  function onTimeUpdate() {
    const v = videoRef.current;
    if (!v || !v.duration || !isFinite(v.duration)) return;
    setProgress(v.currentTime / v.duration);
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="intro-video"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.45, ease: "easeOut" }}
          className="fixed inset-0 z-[100] bg-black"
          role="dialog"
          aria-label="Ball Knowledge Oracle intro video"
          data-testid="intro-video"
        >
          {/* Background poster — shown until the video has decoded enough
              to display a frame. The poster never overlays a playing
              frame; the browser swaps to live frames automatically. */}
          <video
            ref={videoRef}
            src={src}
            poster={poster}
            autoPlay
            muted
            playsInline
            preload="auto"
            onCanPlay={() => {
              setReady(true);
              setBuffering(false);
            }}
            onPlaying={() => setBuffering(false)}
            onWaiting={() => setBuffering(true)}
            onStalled={() => setBuffering(true)}
            onLoadedData={() => setBuffering(false)}
            onEnded={skip}
            onError={skip}
            onTimeUpdate={onTimeUpdate}
            className="absolute inset-0 h-full w-full object-cover"
            aria-hidden="true"
          />

          {/* Cinematic vignette + soft tint at the very start so the poster
              transition feels intentional, not stark. */}
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.45) 100%)",
            }}
          />

          {/* Top-right controls */}
          <div className="absolute right-5 top-5 flex items-center gap-2 md:right-7 md:top-7">
            <motion.button
              type="button"
              onClick={toggleMute}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.94 }}
              aria-label={muted ? "Unmute video" : "Mute video"}
              title={muted ? "Unmute" : "Mute"}
              className="relative inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/20 bg-black/45 text-white backdrop-blur-md transition-colors hover:bg-black/65 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
            >
              {muted ? (
                <>
                  <VolumeX className="h-4 w-4" />
                  <span
                    aria-hidden="true"
                    className="absolute inset-0 animate-ping rounded-full border border-[rgba(255,106,31,0.6)] opacity-70"
                  />
                </>
              ) : (
                <Volume2 className="h-4 w-4" />
              )}
            </motion.button>

            <motion.button
              type="button"
              onClick={skip}
              whileHover={{ scale: 1.03, y: -1 }}
              whileTap={{ scale: 0.96 }}
              aria-label="Skip intro video"
              title="Skip intro (Esc)"
              className="inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-black/45 px-3.5 py-2 text-[11.5px] font-medium uppercase tracking-[0.15em] text-white backdrop-blur-md transition-colors hover:bg-black/65 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
            >
              <SkipForward className="h-3.5 w-3.5" />
              Skip
            </motion.button>
          </div>

          {/* Bottom-center "tap to unmute" affordance. */}
          <AnimatePresence>
            {muted && (
              <motion.button
                key="unmute-hint"
                type="button"
                onClick={toggleMute}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
                transition={{ delay: 0.4, duration: 0.35 }}
                aria-label="Unmute video"
                className="absolute left-1/2 bottom-12 -translate-x-1/2 inline-flex items-center gap-2.5 rounded-full border border-white/25 bg-black/55 px-5 py-3 text-[13px] font-medium text-white backdrop-blur-md transition-colors hover:bg-black/75 hover:border-[rgba(255,106,31,0.55)] focus:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
              >
                <VolumeX className="h-4 w-4" />
                <span>Tap to unmute</span>
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{
                    background: "#ff6a1f",
                    boxShadow: "0 0 10px #ff6a1f",
                  }}
                />
              </motion.button>
            )}
          </AnimatePresence>

          {/* Buffering indicator — only shows when the player has actually
              stalled, so it doesn't get in the way during normal playback. */}
          <AnimatePresence>
            {buffering && (
              <motion.div
                key="buffering"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="pointer-events-none absolute inset-0 flex items-center justify-center"
              >
                <div className="flex items-center gap-2 rounded-full border border-white/15 bg-black/55 px-4 py-2 text-[12px] uppercase tracking-[0.18em] text-white/85 backdrop-blur-md">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Loading
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Slim ember progress bar at the bottom. */}
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[2px] bg-white/10">
            <div
              className="h-full transition-[width] duration-150"
              style={{
                width: `${progress * 100}%`,
                background: "linear-gradient(90deg,#ff8a3d,#ff6a1f)",
                boxShadow: "0 0 12px rgba(255,106,31,0.75)",
              }}
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
