"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { postAsk, getHealth } from "@/lib/api";
import { buildLoreResponse, isSelfQuestion } from "@/lib/oracleLore";
import { ChatInput, type ChatInputHandle } from "@/components/ChatInput";
import { GalaxyBackground } from "@/components/GalaxyBackground";
import { Header } from "@/components/Header";
import { Hero } from "@/components/Hero";
import { IntroVideo } from "@/components/IntroVideo";
import { Sidebar } from "@/components/Sidebar";
import { TurnCard, type Turn } from "@/components/TurnCard";

export default function Home() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [healthOk, setHealthOk] = useState<boolean | null>(null);
  // Bumped on each return-home so the Hero's typewriter intro restarts.
  const [heroKey, setHeroKey] = useState(0);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<ChatInputHandle>(null);

  useEffect(() => {
    getHealth()
      .then((h) => setHealthOk(h.db_ok && h.status === "ok"))
      .catch(() => setHealthOk(false));
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function handleSubmit(question: string) {
    const idx = turns.length;
    setTurns((t) => [...t, { question, status: "pending" }]);
    setSelected(idx);

    // Lore intercept: questions about the Oracle itself never touch the RAG
    // pipeline. We synthesize an AskResponse-shaped object and resolve the
    // turn immediately so it renders through the standard TurnCard path.
    if (isSelfQuestion(question)) {
      const t0 = performance.now();
      // A short, deliberate "thinking" pause sells the bit — the Oracle is
      // not consulting databases, but it's also not blurting.
      await new Promise((resolve) => setTimeout(resolve, 650));
      const response = buildLoreResponse(question, performance.now() - t0);
      setTurns((t) =>
        t.map((x, i) => (i === idx ? { ...x, status: "ok", response } : x)),
      );
      return;
    }

    try {
      const response = await postAsk({ question });
      setTurns((t) =>
        t.map((x, i) => (i === idx ? { ...x, status: "ok", response } : x)),
      );
    } catch (err) {
      setTurns((t) =>
        t.map((x, i) =>
          i === idx
            ? {
                ...x,
                status: "error",
                error: err instanceof Error ? err.message : String(err),
              }
            : x,
        ),
      );
    }
  }

  function handleSuggestion(q: string) {
    inputRef.current?.setValue(q);
  }

  function handleHome() {
    setTurns([]);
    setSelected(null);
    setHeroKey((k) => k + 1);
  }

  const pending = turns.some((t) => t.status === "pending");
  const selectedTurn = selected !== null ? turns[selected] : undefined;
  const isEmpty = turns.length === 0;

  return (
    <div className="relative isolate flex h-screen flex-col text-text">
      {/* Animated galaxy backdrop — fixed behind every layer. The wrapper is
          transparent so this shows through; the body still has the base
          color underneath as a fallback. */}
      <div className="pointer-events-none fixed inset-0 -z-10">
        <GalaxyBackground />
      </div>

      <IntroVideo />
      <Header healthOk={healthOk} canGoHome={!isEmpty} onHome={handleHome} />

      <div className="grid flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[1fr_440px]">
        {/* Chat / Hero column */}
        <div className="flex flex-col overflow-hidden border-r hairline">
          <AnimatePresence mode="wait" initial={false}>
            {isEmpty ? (
              <motion.div
                key={`hero-${heroKey}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.4 }}
                className="relative flex-1 overflow-hidden"
              >
                <Hero onSuggestion={handleSuggestion} runKey={heroKey} />
              </motion.div>
            ) : (
              <motion.div
                key="convo"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35 }}
                className="flex-1 overflow-y-auto px-4 py-6"
              >
                <div className="mx-auto flex max-w-2xl flex-col gap-4">
                  {turns.map((turn, i) => (
                    <TurnCard
                      key={i}
                      turn={turn}
                      index={i}
                      isSelected={selected === i}
                      onSelect={() => setSelected(i)}
                    />
                  ))}
                  <div ref={chatEndRef} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="relative border-t hairline bg-bg/80 backdrop-blur-xl">
            <div className="pointer-events-none absolute -top-8 left-0 right-0 h-8 bg-gradient-to-b from-transparent to-bg/80" />
            <div className="mx-auto max-w-2xl px-4 py-4">
              <ChatInput
                ref={inputRef}
                onSubmit={handleSubmit}
                disabled={pending}
                big={isEmpty}
              />
              {!isEmpty && (
                <div className="mt-2 text-center text-[11px] text-text-dim">
                  The Oracle can be wrong. Stats are SQL-verified; prose carries
                  citations to source articles.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Trace sidebar */}
        <aside className="relative hidden flex-col overflow-hidden bg-bg-elev lg:flex">
          <Sidebar turn={selectedTurn} />
        </aside>
      </div>
    </div>
  );
}
