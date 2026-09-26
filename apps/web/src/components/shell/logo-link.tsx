"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { parseFilters, toSearchParams, withFilters } from "@/lib/params";

/** The logo is lower-case "tally ai" in one colour and one weight, with the accent dot (spec 7.2). */
export function Logo({ href }: { href: string }) {
  return (
    <Link href={href} className="flex shrink-0 items-center gap-2 pr-2 font-semibold tracking-tight">
      <span aria-hidden className="size-2.5 rounded-full bg-primary" />
      tally ai
    </Link>
  );
}

/** The logo opens the overview with the period and accounts, as the Overview link does. */
export function LogoLink() {
  const search = useSearchParams();
  return <Logo href={withFilters("/", parseFilters(toSearchParams(search)))} />;
}
