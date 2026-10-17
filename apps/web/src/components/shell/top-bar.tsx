import { Suspense } from "react";

import { filterContext, reviewCount } from "@/lib/api";

import { FilterBar } from "./filter-bar";
import { Logo, LogoLink } from "./logo-link";
import { MoreMenu } from "./more-menu";
import { NavLinks } from "./nav-links";

/** Logo, navigation and filters (spec 7.2; mockup 02). */
export async function TopBar() {
  const [pending, { accounts, latestDay }] = await Promise.all([reviewCount(), filterContext()]);
  return (
    <header className="border-b">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3 sm:px-6">
        {/* These read the URL: without Suspense, `next build` fails on the prerendered 404 page,
            which keeps a plain logo home. */}
        <Suspense fallback={<Logo href="/" />}>
          <LogoLink />
        </Suspense>
        <Suspense fallback={null}>
          <NavLinks pending={pending} />
        </Suspense>
        {/* Filters (only on the pages they scope), then the menu, always last. */}
        <div className="ml-auto flex items-center gap-2">
          <Suspense fallback={null}>
            <FilterBar accounts={accounts} latestDay={latestDay} />
          </Suspense>
          <MoreMenu />
        </div>
      </div>
    </header>
  );
}
