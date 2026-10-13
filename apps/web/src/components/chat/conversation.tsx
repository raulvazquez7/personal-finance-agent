"use client";

import { useChat } from "@ai-sdk/react";
import { ArrowDown } from "lucide-react";
import { useState } from "react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";

import { Button } from "@/components/ui/button";
import type { ChatMessage } from "@/lib/chat";
import { threadTitle } from "@/lib/chat-threads";

import { ChatHeader } from "./chat-header";
import { ChatMessageView } from "./chat-message";
import { useChats } from "./chats-provider";

/** One chat and its full history (spec 8). */
export function Conversation({ threadId, history }: { threadId: string; history: ChatMessage[] }) {
  const { threads, chatFor } = useChats();
  const [chat] = useState(() => chatFor(threadId, history));
  const { messages } = useChat({ chat });
  const thread = threads.find((t) => t.id === threadId);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <ChatHeader>
        <h1 className="min-w-0 flex-1 truncate font-semibold tracking-tight">{thread ? threadTitle(thread) : "Chat"}</h1>
      </ChatHeader>
      <StickToBottom className="relative min-h-0 flex-1" initial="instant" resize="smooth" role="log" aria-label="Conversation">
        <StickToBottom.Content className="mx-auto flex w-full max-w-3xl flex-col gap-6 py-2">
          {messages.map((message) => (
            <ChatMessageView key={message.id} message={message} live={false} />
          ))}
        </StickToBottom.Content>
        <ScrollToLatest />
      </StickToBottom>
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
      onClick={() => void scrollToBottom()}
    >
      <ArrowDown />
    </Button>
  );
}
