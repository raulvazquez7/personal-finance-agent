import type { Metadata } from "next";

import { ChatsProvider } from "@/components/chat/chats-provider";
import { ThreadList } from "@/components/chat/thread-list";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { ApiError } from "@/lib/api";
import { listThreads } from "@/lib/chat-api";
import type { Thread } from "@/lib/chat";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Chat" };

/** The chat (spec 10): saved chats on the left, the open chat on the right. It fills the window
 * below the top bar (the root layout's `has-data-[slot=chat-shell]` classes), so only the
 * messages scroll. Without an xAI key the API answers 503 and the page says how to set it up. */
export default async function ChatLayout({ children }: LayoutProps<"/chat">) {
  let threads: Thread[];
  try {
    threads = await listThreads();
  } catch (error) {
    if (error instanceof ApiError && error.status === 503) return <NotConfigured />;
    throw error;
  }
  return (
    <ChatsProvider initialThreads={threads}>
      <div data-slot="chat-shell" className="flex min-h-0 flex-1 gap-6">
        <aside className="hidden w-60 shrink-0 flex-col md:flex">
          <ThreadList />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">{children}</div>
      </div>
    </ChatsProvider>
  );
}

function NotConfigured() {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyTitle render={<h1 />}>The chat is not set up yet</EmptyTitle>
        <EmptyDescription>
          It needs an xAI API key. Add XAI_API_KEY to the .env file at the repo root, then restart the API (from apps/api: uv
          run task api).
        </EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}
