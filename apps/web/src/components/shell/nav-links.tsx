"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { filterParams, parseFilters, toSearchParams } from "@/lib/params";
import { cn } from "@/lib/utils";

type Item = { href: string; label: string; keepsFilters: boolean; active: (path: string) => boolean };

const ITEMS: Item[] = [
  {
    href: "/",
    label: "Overview",
    keepsFilters: true,
    // The group, category, merchant and income pages sit under the overview (mockup 03).
    active: (path) => path === "/" || ["/spending", "/income", "/merchants"].some((p) => path.startsWith(p)),
  },
  { href: "/transactions", label: "Transactions", keepsFilters: true, active: (path) => path.startsWith("/transactions") },
  { href: "/subscriptions", label: "Subscriptions", keepsFilters: false, active: (path) => path.startsWith("/subscriptions") },
  { href: "/review", label: "Review", keepsFilters: false, active: (path) => path.startsWith("/review") },
  { href: "/imports", label: "Imports", keepsFilters: false, active: (path) => path.startsWith("/imports") },
  { href: "/settings", label: "Settings", keepsFilters: false, active: (path) => path.startsWith("/settings") },
];

/** The top navigation with a pill for the active item (spec 7.2). The pages that the period and
 * account filters scope keep them in their links. On phones the row scrolls sideways. */
export function NavLinks({ pending }: { pending: number | null }) {
  const pathname = usePathname();
  const search = useSearchParams();
  const query = filterParams(parseFilters(toSearchParams(search))).toString();
  return (
    <nav
      aria-label="Main"
      className="order-last -mx-1 flex w-full items-center gap-1 overflow-x-auto px-1 text-sm sm:order-none sm:w-auto sm:flex-1"
    >
      {ITEMS.map((item) => {
        const active = item.active(pathname);
        return (
          <Link
            key={item.href}
            href={item.keepsFilters && query ? `${item.href}?${query}` : item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "shrink-0 rounded-full px-3 py-1.5 text-muted-foreground transition-colors hover:text-foreground",
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
  );
}
