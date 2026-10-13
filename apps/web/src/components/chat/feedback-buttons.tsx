"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";
import { Textarea } from "@/components/ui/textarea";
import { sendFeedback } from "@/lib/chat-api";

type Value = "up" | "down";

const COMMENT_MAX = 1000; // FeedbackBody.comment (plan 4a, Task 12)

/** Thumbs on an answer (spec 8 and 11): up is sent at once; down asks for an optional comment
 * first, so one request carries both. The answer's trace in Langfuse gets the score. */
export function FeedbackButtons({ messageId, value, onSaved }: { messageId: string; value: Value | null; onSaved: (value: Value) => void }) {
  const [open, setOpen] = useState(false);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  async function save(next: Value, text?: string) {
    setBusy(true);
    try {
      await sendFeedback(messageId, next, text || undefined);
      onSaved(next);
      setOpen(false);
      setComment("");
      toast.success("Thanks for the feedback");
    } catch {
      toast.error("Could not save the feedback.");
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void save("down", comment.trim());
  }

  return (
    <div role="group" aria-label="Rate this answer" className="flex gap-1">
      {/* The clicked control keeps focus while saving (aria-disabled, clicks ignored): a disabled
          button would drop it to the page. */}
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label="Good answer"
        aria-pressed={value === "up"}
        disabled={busy}
        focusableWhenDisabled
        onClick={() => save("up")}
      >
        <ThumbsUp className={value === "up" ? "fill-current" : undefined} />
      </Button>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          render={<Button variant="ghost" size="icon-sm" aria-label="Bad answer" aria-pressed={value === "down"} disabled={busy} />}
        >
          <ThumbsDown className={value === "down" ? "fill-current" : undefined} />
        </PopoverTrigger>
        <PopoverContent align="start" className="w-80">
          <form onSubmit={onSubmit} className="flex flex-col gap-2">
            <PopoverTitle render={<label htmlFor={`feedback-${messageId}`} />}>What was wrong? (optional)</PopoverTitle>
            <Textarea
              id={`feedback-${messageId}`}
              value={comment}
              maxLength={COMMENT_MAX}
              placeholder="A wrong number, a missed note…"
              onChange={(event) => setComment(event.target.value)}
            />
            <Button type="submit" size="sm" className="self-end" disabled={busy} focusableWhenDisabled>
              Send
            </Button>
          </form>
        </PopoverContent>
      </Popover>
    </div>
  );
}
