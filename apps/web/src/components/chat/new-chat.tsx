"use client";

import { MessagesSquare } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { chatErrorText } from "@/lib/chat";
import { createThread } from "@/lib/chat-api";

import { ChatHeader } from "./chat-header";
import { useChats } from "./chats-provider";
import { Composer } from "./composer";

const EXAMPLES = [
  "How much did I spend last month?",
  "Which merchants did I spend the most at this year?",
  "What are my active subscriptions and what do they cost per month?",
  "Compare my spending by group this month with last month.",
];

/** /chat: a new chat. The thread is created with the first question, whose answer starts
 * streaming here and goes on in /chat/<id> (the same useChat `Chat`, from ChatsProvider). */
export function NewChat() {
  const { added, chatFor } = useChats();
  const router = useRouter();
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start(text: string) {
    setPending(true);
    setError(null);
    try {
      const thread = await createThread();
      added(thread);
      void chatFor(thread.id, []).sendMessage({ text });
      router.push(`/chat/${thread.id}`);
    } catch (failure) {
      setError(chatErrorText(failure instanceof Error ? failure : new Error(String(failure))));
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <ChatHeader>
        <h1 className="min-w-0 flex-1 truncate font-semibold tracking-tight">New chat</h1>
      </ChatHeader>
      <Empty className="min-h-0 justify-center-safe overflow-y-auto">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <MessagesSquare />
          </EmptyMedia>
          <EmptyTitle>Ask about your money</EmptyTitle>
          <EmptyDescription>
            Answers come from your imported statements, with how they were counted. Each answer shows the queries it ran.
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent className="max-w-md">
          {EXAMPLES.map((example) => (
            <Button
              key={example}
              variant="secondary"
              className="h-auto w-full justify-start py-2 text-left text-pretty whitespace-normal data-disabled:opacity-50"
              disabled={pending}
              focusableWhenDisabled
              onClick={() => start(example)}
            >
              {example}
            </Button>
          ))}
        </EmptyContent>
      </Empty>
      {error ? (
        <p role="alert" className="mx-auto w-full max-w-3xl rounded-xl bg-card px-4 py-3 text-sm text-bad">
          {error}
        </p>
      ) : null}
      <div className="mx-auto w-full max-w-3xl">
        <Composer value={draft} onChange={setDraft} onSend={start} answering={false} pending={pending} />
      </div>
    </div>
  );
}
