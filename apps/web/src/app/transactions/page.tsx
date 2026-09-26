import { apiGet, type Schemas } from "@/lib/api";
import { money, rangeLabel, signedMoney } from "@/lib/format";
import { plural } from "@/lib/labels";
import { explorerParams, parseExplorer, parseFilters } from "@/lib/params";

import { ExplorerFilters } from "./explorer-filters";
import { TransactionList } from "./transaction-list";

export const dynamic = "force-dynamic";

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
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h1 className="text-xl font-semibold tracking-tight">Transactions</h1>
        {/* nowrap: a narrow screen may break between "+" and "€", splitting the sign from its amount.
            "out" already gives money out its direction, so it takes no sign. */}
        <p className="text-sm text-muted-foreground">
          {rangeLabel(page.period)} · {plural(page.count, "transaction", "transactions")} ·{" "}
          <span className="whitespace-nowrap text-income">{signedMoney(page.money_in)}</span> in ·{" "}
          <span className="whitespace-nowrap">{money(page.money_out)}</span> out
        </p>
      </header>
      <ExplorerFilters search={search} explorer={explorer} categories={categories} merchants={merchants} />
      <TransactionList key={search} initial={page} search={search} categories={categories} merchants={merchants} />
    </>
  );
}
