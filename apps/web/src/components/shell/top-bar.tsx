import Link from "next/link";
import { Suspense } from "react";

import { filterContext, reviewCount } from "@/lib/api";

import { FilterBar } from "./filter-bar";
import { NavLinks } from "./nav-links";

/** Logo, navigation and filters (spec 7.2; mockup 02). The logo is lower-case "tally ai" in one
 * colour and one weight, with the accent dot. */
export async function TopBar() {
  const [pending, { accounts, latestDay }] = await Promise.all([reviewCount(), filterContext()]);
  return (
    <header className="border-b">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2 pr-2 font-semibold tracking-tight">
          <span aria-hidden className="size-2.5 rounded-full bg-primary" />
          tally ai
        </Link>
        {/* Both read the URL: without Suspense, `next build` fails on the prerendered 404 page. */}
        <Suspense fallback={null}>
          <NavLinks pending={pending} />
        </Suspense>
        <Suspense fallback={null}>
          <FilterBar accounts={accounts} latestDay={latestDay} />
        </Suspense>
      </div>
    </header>
  );
}
