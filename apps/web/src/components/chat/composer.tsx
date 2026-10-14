"use client";

import { ArrowUp, Square } from "lucide-react";
import { useRef, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

const TEXT_MAX = 4000; // NewMessage.text in apps/api/finance/api/chat.py: 1-4000 characters

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSend: (text: string) => void;
  /** An answer is on its way: the button stops it instead of sending. */
  answering: boolean;
  onStop?: () => void;
  /** A request that is not an answer (creating the chat) is running. */
  pending?: boolean;
};

/** The question box: Enter sends, Shift+Enter starts a new line, and Stop ends an answer. */
export function Composer({ value, onChange, onSend, answering, onStop, pending = false }: Props) {
  const text = value.trim();
  const canSend = text.length > 0 && !answering && !pending;
  // Send and Stop share one button, which ends up disabled: focus goes back to the box instead
  // of dropping to the page.
  const box = useRef<HTMLTextAreaElement>(null);

  function submit(event: { preventDefault: () => void }) {
    event.preventDefault();
    if (!canSend) return;
    onSend(text);
    box.current?.focus();
  }

  function stop() {
    onStop?.();
    box.current?.focus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Not while an input method composes a character (Japanese, Chinese…).
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) submit(event);
  }

  return (
    <form onSubmit={submit} className="flex shrink-0 items-end gap-2 rounded-2xl border border-input bg-background p-2 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
      <label htmlFor="chat-question" className="sr-only">
        Your question
      </label>
      <Textarea
        id="chat-question"
        ref={box}
        value={value}
        maxLength={TEXT_MAX}
        rows={1}
        placeholder="Ask about your money"
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={onKeyDown}
        className="max-h-48 min-h-9 resize-none border-0 px-2 shadow-none focus-visible:ring-0"
      />
      {answering ? (
        <Button type="button" size="icon" variant="secondary" onClick={stop} aria-label="Stop the answer">
          <Square />
        </Button>
      ) : (
        <Button type="submit" size="icon" disabled={!canSend} aria-label="Send">
          {pending ? <Spinner /> : <ArrowUp />}
        </Button>
      )}
    </form>
  );
}
