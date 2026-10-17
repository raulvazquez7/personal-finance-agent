"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { filterParams, parseFilters, toSearchParams } from "@/lib/params";
import { cn } from "@/lib/utils";

import { ITEMS } from "./nav-links";

/** The same links as the desktop row, behind a menu that only shows below `sm`. */
export function MobileNav({ pending }: { pending: number | null }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const search = useSearchParams();
  const query = filterParams(parseFilters(toSearchParams(search))).toString();

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={<Button variant="ghost" size="icon-sm" className="sm:hidden" aria-label="Menu" />}
      >
        <Menu />
      </SheetTrigger>
      <SheetContent side="left">
        <SheetHeader>
          <SheetTitle>Menu</SheetTitle>
        </SheetHeader>
        <nav aria-label="Main" className="flex flex-col gap-1 px-2">
          {ITEMS.map((item) => {
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
          })}
        </nav>
      </SheetContent>
    </Sheet>
  );
}
