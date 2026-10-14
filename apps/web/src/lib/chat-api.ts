import { DefaultChatTransport } from "ai";

import { API_URL, apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api";
import { newMessageBody, type ChatMessage, type ChatUIMessage, type Thread } from "@/lib/chat";

/** The chat routes in apps/api/finance/api/chat.py. Every one answers 503 while the chat is not set up. */
export const listThreads = () => apiGet<Thread[]>("/chat/threads");
export const listMessages = (threadId: string) => apiGet<ChatMessage[]>(`/chat/threads/${threadId}/messages`);
export const createThread = () => apiPost<Thread>("/chat/threads");
export const renameThread = (threadId: string, title: string) => apiPatch<Thread>(`/chat/threads/${threadId}`, { title });
export const deleteThread = (threadId: string) => apiDelete(`/chat/threads/${threadId}`);
export const sendFeedback = (messageId: string, value: "up" | "down", comment?: string) =>
  apiPost(`/chat/messages/${messageId}/feedback`, { value, comment });

/** useChat's transport. A chat's id is its thread id; the answer streams from that thread's
 * messages route, and only the new question is sent (spec 10). */
export const chatTransport = new DefaultChatTransport<ChatUIMessage>({
  prepareSendMessagesRequest: ({ id, messages }) => ({
    api: `${API_URL}/chat/threads/${id}/messages`,
    body: newMessageBody(messages),
  }),
});
