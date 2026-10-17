import { Info } from "lucide-react";
import type { Metadata } from "next";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { apiGet, type Schemas } from "@/lib/api";
import { money, rangeLabel, signedMoney } from "@/lib/format";
import { plural } from "@/lib/labels";
import { explorerParams, parseExplorer, parseFilters } from "@/lib/params";

import { ExplorerFilters } from "./explorer-filters";
import { TransactionList } from "./transaction-list";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Transactions" };

/** The explorer (spec 7.3): any row can be found, understood and corrected in the side panel.
 * The page URL and the API take the same params, so one sanitized query string serves both. */
export default async function TransactionsPage({ searchParams }: PageProps<"/transactions">) {
  const query = await searchParams;
  const explorer = parseExplorer(query);
  const search = explorerParams(parseFilters(query), explorer).toString();
  const [page, categories, merchants] = await Promise.all([
    apiGet<Schemas["TransactionPage"]>(`/transactions?${search}`),
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["MerchantOut"][]>("/merchants?limit=5000"),
  ]);
  return (
    <>
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <h1 className="text-xl font-semibold tracking-tight">Transactions</h1>
        {/* nowrap: a narrow screen may break between "+" and "€", splitting the sign from its amount.
            "out" already gives money out its direction, so it takes no sign. */}
        <p className="text-sm text-muted-foreground">
          {rangeLabel(page.period)} · {plural(page.count, "transaction", "transactions")} ·{" "}
          <span className="whitespace-nowrap text-income">{signedMoney(page.money_in)}</span> in ·{" "}
          <span className="whitespace-nowrap">{money(page.money_out)}</span> out
          {Number(page.transfers) > 0 ? ` · incl. ${money(page.transfers)} transfers` : null}{" "}
          {/* Inside the sentence, so a narrow screen does not leave the button alone on a line. */}
          <Popover>
            <PopoverTrigger
              render={<Button variant="ghost" size="icon-xs" aria-label="What these totals include" />}
            >
              <Info />
            </PopoverTrigger>
            <PopoverContent align="end" className="w-80">
              In and out are cash flow: every credit and debit in this list, including transfers and
              refunds. Income and expenses on Overview leave transfers out, and a refund reduces the
              spending of its category.
            </PopoverContent>
          </Popover>
        </p>
      </header>
      <ExplorerFilters search={search} explorer={explorer} categories={categories} merchants={merchants} />
      <TransactionList key={search} initial={page} search={search} categories={categories} merchants={merchants} />
    </>
  );
}
