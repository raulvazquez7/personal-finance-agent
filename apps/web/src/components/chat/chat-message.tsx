"use client";

import { Streamdown } from "streamdown";

import { answerBlocks, type ChatUIMessage } from "@/lib/chat";

import { FeedbackButtons } from "./feedback-buttons";
import { QueryDisclosure } from "./query-disclosure";

type Props = {
  message: ChatUIMessage;
  /** The answer that is streaming now: its markdown is still incomplete. */
  live: boolean;
  onFeedback: (messageId: string, value: "up" | "down") => void;
};

/** One message: the user's question as a bubble, or an answer as markdown with its queries. */
export function ChatMessageView({ message, live, onFeedback }: Props) {
  if (message.role === "user") {
    const text = message.parts.map((part) => (part.type === "text" ? part.text : "")).join("");
    return <div className="ml-auto max-w-[85%] rounded-2xl bg-card px-4 py-2.5 whitespace-pre-wrap wrap-anywhere">{text}</div>;
  }
  const meta = message.metadata;
  return (
    <article aria-label="Answer" className="flex min-w-0 flex-col gap-3">
      {answerBlocks(message.parts).map((block, index) =>
        block.kind === "queries" ? (
          <QueryDisclosure key={index} queries={block.queries} />
        ) : (
          <Streamdown
            key={index}
            isAnimating={live && block.streaming}
            controls={false}
            // No images: an image in an answer would make the browser send a request, and any data in
            // its URL, to another host.
            disallowedElements={["img"]}
            // Tables show in full; on a phone they scroll sideways in their own box.
            tableMaxHeight={Number.POSITIVE_INFINITY}
            // Headings stay small: an answer's "How I counted it" is a note, not a page title.
            // Cells keep an amount on one line.
            className="[&_:is(h1,h2,h3,h4)]:mt-4 [&_:is(h1,h2,h3,h4)]:text-base [&_:is(td,th)]:whitespace-nowrap"
          >
            {block.text}
          </Streamdown>
        ),
      )}
      {meta?.status === "stopped" ? <p className="text-sm text-muted-foreground">You stopped this answer.</p> : null}
      {meta?.status === "error" ? <p className="text-sm text-muted-foreground">This answer did not finish.</p> : null}
      {meta?.status === "ok" ? (
        <FeedbackButtons messageId={message.id} value={meta.feedback} onSaved={(value) => onFeedback(message.id, value)} />
      ) : null}
    </article>
  );
}
