"use client";

import { PanelLeft } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

import { ThreadList } from "./thread-list";

/** The chat's title row: the page's heading and actions. Below md the sidebar is a sheet,
 * opened from here. */
export function ChatHeader({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <header className="flex min-h-9 shrink-0 items-center gap-2">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger render={<Button variant="ghost" size="icon" className="md:hidden" aria-label="Chats" />}>
          <PanelLeft />
        </SheetTrigger>
        <SheetContent side="left" className="data-[side=left]:w-72">
          <SheetHeader>
            <SheetTitle>Chats</SheetTitle>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col px-4 pb-4">
            <ThreadList onNavigate={() => setOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>
      {children}
    </header>
  );
}
