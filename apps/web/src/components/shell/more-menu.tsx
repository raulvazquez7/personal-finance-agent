"use client";

import { Menu } from "@base-ui/react/menu";
import { Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

import { MORE_ITEMS } from "./nav-links";

/** Imports and Settings, behind one button at the end of the top bar (spec section 3). The items
 * are Base UI link items: real links (they open in a new tab), announced as menu items. */
export function MoreMenu() {
  const pathname = usePathname();
  const active = MORE_ITEMS.some((item) => item.active(pathname));

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="secondary"
            size="icon-sm"
            aria-label="Imports and settings"
            // Below lg the sheet lists these pages. On them, the button takes the active pill's colours.
            className={cn(
              "hidden rounded-full lg:inline-flex",
              active && "bg-foreground text-background hover:bg-foreground/90",
            )}
          />
        }
      >
        <Settings />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        {MORE_ITEMS.map((item) => {
          const current = item.active(pathname);
          return (
            <Menu.LinkItem
              key={item.href}
              closeOnClick
              render={<Link href={item.href} />}
              aria-current={current ? "page" : undefined}
              className="flex items-start gap-2.5 rounded-md px-2 py-1.5 text-sm outline-hidden select-none data-highlighted:bg-accent"
            >
              <item.icon aria-hidden className="mt-0.5 size-4 shrink-0" />
              <span className="flex flex-col">
                <span className={cn(current && "font-medium")}>{item.label}</span>
                <span className="text-xs text-muted-foreground">{item.hint}</span>
              </span>
            </Menu.LinkItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
