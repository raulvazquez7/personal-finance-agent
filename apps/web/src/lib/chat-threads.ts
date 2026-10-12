import type { Thread } from "@/lib/chat";

/** A thread without a title yet: its first answer is still being written, or was stopped. Not
 * "New chat", which names the button that starts one. */
export const threadTitle = (thread: Thread) => thread.title ?? "Untitled chat";

/** The sidebar's list, newest activity first like GET /chat/threads: a thread that is created
 * or has just answered moves to the top (a rename keeps its place). */
export const putFirst = (threads: Thread[], thread: Thread) => [thread, ...threads.filter((t) => t.id !== thread.id)];

export const patchThread = (threads: Thread[], id: string, patch: Partial<Thread>) =>
  threads.map((thread) => (thread.id === id ? { ...thread, ...patch } : thread));

export const moveFirst = (threads: Thread[], id: string) => {
  const thread = threads.find((t) => t.id === id);
  return thread ? putFirst(threads, thread) : threads;
};

export const dropThread = (threads: Thread[], id: string) => threads.filter((thread) => thread.id !== id);
