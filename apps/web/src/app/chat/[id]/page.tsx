import { notFound } from "next/navigation";

import { Conversation } from "@/components/chat/conversation";
import { ApiError } from "@/lib/api";
import { listMessages } from "@/lib/chat-api";
import type { ChatMessage } from "@/lib/chat";
import { isUuid } from "@/lib/params";

export const dynamic = "force-dynamic";

/** One saved chat with its full history (spec 8). A deleted or unknown chat is a 404. */
export default async function ChatPage({ params }: PageProps<"/chat/[id]">) {
  const { id } = await params;
  if (!isUuid(id)) notFound();
  let history: ChatMessage[];
  try {
    history = await listMessages(id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  return <Conversation key={id} threadId={id} history={history} />;
}
