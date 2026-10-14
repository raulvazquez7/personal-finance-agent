"use client";

import { PanelLeft } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

import { ThreadList } from "./thread-list";

// Picking a chat in the sheet opens a page with a new header, and the old trigger goes with the
// old page: the new trigger takes the focus, so it never drops to the page. Only when it did drop:
// picking the open chat keeps this header, and the flag outlives it.
let focusTriggerOnMount = false;

/** The chat's title row: the page's heading and actions. Below md the sidebar is a sheet,
 * opened from here. */
export function ChatHeader({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!focusTriggerOnMount) return;
    focusTriggerOnMount = false;
    if (document.activeElement === document.body) trigger.current?.focus();
  }, []);
  return (
    <header className="flex min-h-9 shrink-0 items-center gap-2">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger ref={trigger} render={<Button variant="ghost" size="icon" className="md:hidden" aria-label="Chats" />}>
          <PanelLeft />
        </SheetTrigger>
        <SheetContent side="left" className="data-[side=left]:w-72">
          <SheetHeader>
            <SheetTitle>Chats</SheetTitle>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col px-4 pb-4">
            <ThreadList
              onNavigate={() => {
                focusTriggerOnMount = true;
                setOpen(false);
              }}
            />
          </div>
        </SheetContent>
      </Sheet>
      {children}
    </header>
  );
}
