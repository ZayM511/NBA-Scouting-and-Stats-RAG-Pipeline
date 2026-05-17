"use client";

import {
  useState,
  useRef,
  KeyboardEvent,
  useImperativeHandle,
  forwardRef,
} from "react";
import { motion } from "framer-motion";
import { ArrowUp, CornerDownLeft, Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

interface Props {
  onSubmit: (question: string) => void;
  disabled: boolean;
  big?: boolean;
}

export interface ChatInputHandle {
  setValue: (v: string) => void;
  focus: () => void;
}

export const ChatInput = forwardRef<ChatInputHandle, Props>(function ChatInput(
  { onSubmit, disabled, big = false },
  ref,
) {
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({
    setValue: (v: string) => {
      setValue(v);
      const ta = textareaRef.current;
      if (ta) {
        ta.value = v;
        ta.style.height = "auto";
        ta.style.height = `${Math.min(ta.scrollHeight, 240)}px`;
        ta.focus();
      }
    },
    focus: () => textareaRef.current?.focus(),
  }));

  function submit() {
    const q = value.trim();
    if (!q || disabled) return;
    onSubmit(q);
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function autoresize(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setValue(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 240)}px`;
  }

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <motion.div
      initial={false}
      animate={{
        boxShadow: focused
          ? "0 0 0 1.5px rgba(255,106,31,0.55), 0 16px 60px -16px rgba(255,106,31,0.45)"
          : "0 0 0 1px rgba(255,255,255,0.08), 0 8px 30px -12px rgba(0,0,0,0.5)",
      }}
      transition={{ duration: 0.25 }}
      className={cn(
        "group relative flex flex-col rounded-2xl bg-surface/85 backdrop-blur-xl",
        "border hairline overflow-hidden",
      )}
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={autoresize}
        onKeyDown={onKeyDown}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        disabled={disabled}
        placeholder={
          big
            ? "Ask the Ball Knowledge Oracle about a player, stat, or matchup…"
            : "Ask a follow-up. Enter to send, Shift+Enter for newline."
        }
        rows={big ? 2 : 1}
        className={cn(
          "w-full resize-none bg-transparent px-5 pt-4 pb-2 text-text placeholder:text-text-dim",
          "focus:outline-none disabled:opacity-50",
          big ? "text-[16px] leading-7" : "text-[15px] leading-6",
        )}
      />

      <div className="flex items-center justify-between px-3 pb-2.5 pt-1">
        <div className="flex items-center gap-2 pl-2 text-[11px] text-text-dim">
          <span className="inline-flex items-center gap-1 rounded-md border hairline px-1.5 py-0.5">
            <CornerDownLeft className="h-3 w-3" />
            send
          </span>
          <span className="inline-flex items-center gap-1 rounded-md border hairline px-1.5 py-0.5">
            ⇧ ↵ newline
          </span>
          {value.length > 0 && (
            <span className="ml-1 text-text-dim">{value.length} chars</span>
          )}
        </div>

        <button
          type="button"
          onClick={submit}
          disabled={!canSend}
          aria-label="Send question"
          className={cn(
            "relative inline-flex h-9 w-9 items-center justify-center rounded-xl transition-all",
            canSend
              ? "bg-[linear-gradient(180deg,#ff8a3d,#f15a10)] text-white shadow-[0_8px_30px_-8px_rgba(255,106,31,0.65),inset_0_1px_0_rgba(255,255,255,0.35)] hover:brightness-110 active:scale-95"
              : "bg-surface-2 text-text-dim cursor-not-allowed",
          )}
        >
          {disabled ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ArrowUp className="h-4 w-4" />
          )}
        </button>
      </div>
    </motion.div>
  );
});
