"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { apiGet, type Schemas } from "@/lib/api";
import { filterParams, parseFilters, toSearchParams } from "@/lib/params";

import { AccountPicker } from "./account-picker";
import { PeriodPicker } from "./period-picker";

const FILTERED = ["/transactions", "/spending", "/income", "/merchants"];

type Props = { accounts: Schemas["Account"][]; latestDay: string | null };

/** The filters on the right of the top bar (spec 7.2), only on the pages they scope. The default
 * month is the latest one with data for the selected accounts (spec 2.6). `latestDay` comes from
 * the root layout, which does not re-render on client navigation, so it is right only without an
 * account filter; with one, the latest day of those accounts is fetched here (Decision F), and the
 * pill and the page always show the same month. */
export function FilterBar({ accounts, latestDay }: Props) {
  const pathname = usePathname();
  const search = useSearchParams();
  const shown = pathname === "/" || FILTERED.some((path) => pathname.startsWith(path));
  // Only the account_id params: the period does not change the latest day.
  const accountQuery = filterParams({ period: "month", accounts: parseFilters(toSearchParams(search)).accounts }).toString();
  const [filtered, setFiltered] = useState<{ query: string; latestDay: string | null } | null>(null);

  useEffect(() => {
    if (!shown || !accountQuery) return;
    const controller = new AbortController();
    apiGet<Schemas["TransactionPage"]>(`/transactions?limit=1&${accountQuery}`, { signal: controller.signal }).then(
      (page) => setFiltered({ query: accountQuery, latestDay: page.period.latest_day }),
      () => {}, // aborted by a newer selection, or the API is down: the pill reads "Latest month"
    );
    return () => controller.abort();
  }, [shown, accountQuery]);

  if (!shown) return null;
  const day = !accountQuery ? latestDay : filtered?.query === accountQuery ? filtered.latestDay : null;
  return (
    <div className="ml-auto flex items-center gap-2">
      <AccountPicker accounts={accounts} />
      <PeriodPicker latestDay={day} />
    </div>
  );
}
