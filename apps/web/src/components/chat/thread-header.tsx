"use client";

import { Pencil, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { flushSync } from "react-dom";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import type { Thread } from "@/lib/chat";
import { deleteThread, renameThread } from "@/lib/chat-api";
import { threadTitle } from "@/lib/chat-threads";

import { ChatHeader } from "./chat-header";
import { useChats } from "./chats-provider";

const TITLE_MAX = 200; // RenameThread.title: 1-200 characters (plan 4a, Task 12)

/** The open chat's title, live as it arrives, with Rename and Delete (spec 8 and 10). Delete
 * waits for the answer to end: the API refuses it with 409 while the chat answers. */
export function ThreadHeader({ thread, answering }: { thread: Thread; answering: boolean }) {
  const { renamed, deleted } = useChats();
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const renameButton = useRef<HTMLButtonElement>(null);

  function stopEditing() {
    // The field goes away: keyboard focus returns to Rename instead of the page.
    flushSync(() => setEditing(false));
    renameButton.current?.focus();
  }

  async function onRename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      renamed(await renameThread(thread.id, title.trim()));
      stopEditing();
    } catch {
      toast.error("Could not rename the chat.");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    setBusy(true);
    try {
      await deleteThread(thread.id);
      deleted(thread.id);
      router.push("/chat");
    } catch (error) {
      toast.error(error instanceof ApiError && error.detail ? error.detail : "Could not delete the chat.");
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <ChatHeader>
        <form onSubmit={onRename} className="flex min-w-0 flex-1 items-center gap-2">
          <label htmlFor="chat-title" className="sr-only">
            Chat name
          </label>
          <Input
            id="chat-title"
            value={title}
            maxLength={TITLE_MAX}
            autoFocus
            readOnly={busy}
            onChange={(event) => setTitle(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") stopEditing();
            }}
          />
          <Button type="submit" variant="outline" disabled={busy || !title.trim()} focusableWhenDisabled className="data-disabled:opacity-50">
            Save
          </Button>
          <Button type="button" variant="ghost" onClick={stopEditing}>
            Cancel
          </Button>
        </form>
      </ChatHeader>
    );
  }

  return (
    <ChatHeader>
      <h1 className="min-w-0 flex-1 truncate font-semibold tracking-tight">{threadTitle(thread)}</h1>
      <Button
        ref={renameButton}
        variant="ghost"
        size="icon"
        aria-label="Rename this chat"
        onClick={() => {
          setTitle(threadTitle(thread));
          setEditing(true);
        }}
      >
        <Pencil />
      </Button>
      <AlertDialog>
        <AlertDialogTrigger render={<Button variant="ghost" size="icon" aria-label="Delete this chat" disabled={answering || busy} />}>
          <Trash2 />
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this chat?</AlertDialogTitle>
            <AlertDialogDescription>“{threadTitle(thread)}” and all its messages are deleted. This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={onDelete} disabled={busy} focusableWhenDisabled className="data-disabled:opacity-50">
              {busy ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ChatHeader>
  );
}
