"use client";

import { Chat } from "@ai-sdk/react";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { toUIMessages, type ChatMessage, type ChatPart, type ChatUIMessage, type Thread } from "@/lib/chat";
import { chatTransport } from "@/lib/chat-api";
import { dropThread, moveFirst, patchThread, putFirst } from "@/lib/chat-threads";

type Chats = {
  threads: Thread[];
  /** The live conversation of a thread: the same instance across navigations, so an answer keeps
   * streaming when a new chat moves from /chat to /chat/<id> or the user opens another chat. */
  chatFor: (threadId: string, history: ChatMessage[]) => Chat<ChatUIMessage>;
  added: (thread: Thread) => void;
  renamed: (thread: Thread) => void;
  deleted: (threadId: string) => void;
};

const ChatsContext = createContext<Chats | null>(null);

export function useChats(): Chats {
  const chats = useContext(ChatsContext);
  if (!chats) throw new Error("useChats needs a ChatsProvider (app/chat/layout.tsx)");
  return chats;
}

/** The chat's client state for the /chat layout: the sidebar's threads and one useChat `Chat`
 * per opened thread. The layout's server fetch seeds the list; this keeps it current (new chats,
 * titles as they arrive, renames, deletions, the latest answer on top). */
export function ChatsProvider({ initialThreads, children }: { initialThreads: Thread[]; children: ReactNode }) {
  const [threads, setThreads] = useState(initialThreads);
  const [live] = useState(() => new Map<string, Chat<ChatUIMessage>>());

  const chatFor = useCallback(
    (threadId: string, history: ChatMessage[]) => {
      const existing = live.get(threadId);
      if (existing) return existing;
      const chat: Chat<ChatUIMessage> = new Chat<ChatUIMessage>({
        id: threadId,
        messages: toUIMessages(history),
        transport: chatTransport,
        onData: (part) => {
          if (part.type === "data-title") setThreads((all) => patchThread(all, part.data.threadId, { title: part.data.title }));
        },
        onFinish: ({ message, isAbort, isError }) => {
          if (!chat.messages.some((m) => m.id === message.id)) return; // refused before any answer
          // The answer is saved now: it can take feedback, and the thread moves to the top. A stop
          // drops the queries still running, as the API does when it saves the answer.
          const status = isAbort ? "stopped" : isError ? "error" : "ok";
          const kept = (part: ChatPart) => !isAbort || part.type !== "tool-run_sql" || part.state === "output-available";
          chat.messages = chat.messages.map((m) =>
            m.id === message.id ? { ...m, parts: m.parts.filter(kept), metadata: { status, feedback: null } } : m,
          );
          setThreads((all) => moveFirst(all, threadId));
        },
      });
      live.set(threadId, chat);
      return chat;
    },
    [live],
  );

  const value = useMemo<Chats>(
    () => ({
      threads,
      chatFor,
      added: (thread) => setThreads((all) => putFirst(all, thread)),
      renamed: (thread) => setThreads((all) => patchThread(all, thread.id, thread)),
      deleted: (threadId) => {
        live.delete(threadId);
        setThreads((all) => dropThread(all, threadId));
      },
    }),
    [threads, chatFor, live],
  );
  return <ChatsContext.Provider value={value}>{children}</ChatsContext.Provider>;
}
