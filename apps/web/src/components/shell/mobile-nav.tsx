"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { filterParams, parseFilters, toSearchParams } from "@/lib/params";
import { cn } from "@/lib/utils";

import { MAIN_ITEMS, MORE_ITEMS } from "./nav-links";

/** Every page, behind a menu that shows below `lg`: the daily pages, then Imports and Settings. */
export function MobileNav({ pending }: { pending: number | null }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const search = useSearchParams();
  const query = filterParams(parseFilters(toSearchParams(search))).toString();

  const link = (item: (typeof MAIN_ITEMS)[number]) => {
    const active = item.active(pathname);
    return (
      <Link
        key={item.href}
        href={item.keepsFilters && query ? `${item.href}?${query}` : item.href}
        aria-current={active ? "page" : undefined}
        aria-label={item.href === "/review" && pending ? `${item.label}, ${pending} to review` : undefined}
        onClick={() => setOpen(false)}
        className={cn(
          // 44 px tall: a comfortable target for a finger.
          "flex min-h-11 items-center rounded-full px-3 text-muted-foreground hover:text-foreground",
          active && "bg-foreground font-medium text-background hover:text-background",
        )}
      >
        {item.label}
        {item.href === "/review" && pending ? (
          <span className={cn("ml-1.5", !active && "text-primary")}>{pending}</span>
        ) : null}
      </Link>
    );
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger render={<Button variant="ghost" size="icon-sm" className="lg:hidden" aria-label="Menu" />}>
        <Menu />
      </SheetTrigger>
      <SheetContent side="left">
        <SheetHeader>
          <SheetTitle>Menu</SheetTitle>
        </SheetHeader>
        <nav aria-label="Main" className="flex flex-col gap-1 px-2">
          {MAIN_ITEMS.map(link)}
          <Separator className="my-2" />
          {MORE_ITEMS.map(link)}
        </nav>
      </SheetContent>
    </Sheet>
  );
}
