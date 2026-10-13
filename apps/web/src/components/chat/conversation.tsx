"use client";

import { useChat } from "@ai-sdk/react";
import { ArrowDown } from "lucide-react";
import { useEffect, useState } from "react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";

import { Button } from "@/components/ui/button";
import { chatErrorText, isThinking, unanswered, type ChatMessage } from "@/lib/chat";

import { ChatHeader } from "./chat-header";
import { ChatMessageView } from "./chat-message";
import { useChats } from "./chats-provider";
import { Composer } from "./composer";
import { ThreadHeader } from "./thread-header";

/** One chat: its history, the streaming answer, and the question box (spec 10). */
export function Conversation({ threadId, history }: { threadId: string; history: ChatMessage[] }) {
  const { threads, chatFor } = useChats();
  const [chat] = useState(() => chatFor(threadId, history));
  const { messages, status, error, sendMessage, stop, setMessages } = useChat({ chat });
  const [draft, setDraft] = useState("");
  const answering = status === "submitted" || status === "streaming";
  const thread = threads.find((t) => t.id === threadId);
  const last = messages.at(-1);
  const thinking = answering && isThinking(messages);

  useEffect(() => {
    // A new chat arrives here from /chat while it answers; the box it was asked from is gone.
    const answeringOnArrival = chat.status === "submitted" || chat.status === "streaming";
    if (answeringOnArrival && document.activeElement === document.body) document.getElementById("chat-question")?.focus();
  }, [chat]);

  async function send(text: string) {
    setDraft("");
    await sendMessage({ text });
    // A question the API refused or never got goes back to the box, to send again.
    const question = chat.status === "error" ? unanswered(chat.messages) : null;
    if (question !== null) {
      setMessages(chat.messages.slice(0, -1));
      setDraft(question);
    }
  }

  function saveFeedback(messageId: string, value: "up" | "down") {
    setMessages((all) =>
      all.map((m) => (m.id === messageId && m.metadata ? { ...m, metadata: { ...m.metadata, feedback: value } } : m)),
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      {thread ? (
        <ThreadHeader thread={thread} answering={answering} />
      ) : (
        <ChatHeader>
          <h1 className="min-w-0 flex-1 truncate font-semibold tracking-tight">Chat</h1>
        </ChatHeader>
      )}
      <StickToBottom
        className="relative min-h-0 flex-1 rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        initial="instant"
        resize="smooth"
        role="log"
        aria-label="Conversation"
        aria-busy={answering}
        tabIndex={-1}
      >
        <StickToBottom.Content className="mx-auto flex w-full max-w-3xl flex-col gap-6 py-2">
          {messages.map((message) => (
            <ChatMessageView key={message.id} message={message} live={answering && message === last} onFeedback={saveFeedback} />
          ))}
          {thinking ? <p className="shimmer text-sm">Thinking…</p> : null}
          {error ? (
            <p role="alert" className="rounded-xl bg-card px-4 py-3 text-sm text-bad">
              {chatErrorText(error)}
            </p>
          ) : null}
        </StickToBottom.Content>
        <ScrollToLatest />
      </StickToBottom>
      <div className="mx-auto w-full max-w-3xl">
        <Composer value={draft} onChange={setDraft} onSend={send} answering={answering} onStop={() => void stop()} />
      </div>
    </div>
  );
}

function ScrollToLatest() {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();
  if (isAtBottom) return null;
  return (
    <Button
      variant="outline"
      size="icon"
      aria-label="Scroll to the latest message"
      className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full shadow-sm"
      onClick={(event) => {
        // The button disappears once the view is at the bottom: focus moves to the conversation
        // first, so it never drops to the page.
        event.currentTarget.closest<HTMLElement>("[role=log]")?.focus({ preventScroll: true });
        void scrollToBottom();
      }}
    >
      <ArrowDown />
    </Button>
  );
}
