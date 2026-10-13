"use client";

import { SquarePen } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { buttonVariants } from "@/components/ui/button";
import { threadTitle } from "@/lib/chat-threads";
import { cn } from "@/lib/utils";

import { useChats } from "./chats-provider";

/** New chat and the saved chats, newest activity first (spec 10). In the sidebar on wide
 * screens and in a sheet on phones; `onNavigate` closes the sheet. */
export function ThreadList({ onNavigate }: { onNavigate?: () => void }) {
  const { threads } = useChats();
  const pathname = usePathname();
  return (
    <nav aria-label="Chats" className="flex min-h-0 flex-col gap-3">
      <Link href="/chat" onClick={onNavigate} className={cn(buttonVariants({ variant: "outline" }), "justify-start")}>
        <SquarePen data-icon="inline-start" />
        New chat
      </Link>
      {threads.length === 0 ? (
        <p className="px-3 text-sm text-muted-foreground">Your chats appear here.</p>
      ) : (
        <ul className="-mx-1 flex min-h-0 flex-col gap-0.5 overflow-y-auto px-1 pb-1">
          {threads.map((thread) => {
            const active = pathname === `/chat/${thread.id}`;
            return (
              <li key={thread.id}>
                <Link
                  href={`/chat/${thread.id}`}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "block truncate rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                    active && "bg-muted font-medium text-foreground",
                  )}
                >
                  {threadTitle(thread)}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </nav>
  );
}
