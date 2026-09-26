import Link from "next/link";
import { Fragment } from "react";

import { BreakdownTable } from "@/components/breakdown/breakdown-table";
import { CategoryTreemap } from "@/components/charts/category-treemap";
import { DeltaText } from "@/components/money/delta-text";
import { NoData } from "@/components/money/no-data";
import { TransactionTable } from "@/components/transactions/transaction-table";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Schemas } from "@/lib/api";
import { breakdownItems, type BreakdownContext } from "@/lib/breakdown";
import { rampColor } from "@/lib/colors";
import { delta, periodHasData, type Good } from "@/lib/delta";
import { money, previousLabel, rangeLabel, signedMoney } from "@/lib/format";
import { plural } from "@/lib/labels";
import type { Filters } from "@/lib/params";
import { cn } from "@/lib/utils";

import { SpendingCard } from "./spending-card";

export type Crumb = { label: string; href?: string };

type Props = {
  detail: Schemas["SpendingDetail"];
  categories: Schemas["CategoryOut"][];
  filters: Filters;
  title: string;
  crumbs: Crumb[];
  childDimension: "category" | "merchant" | null;
  seeAllHref: string;
  defaultView?: "monthly" | "cumulative";
};

/** One template for every level (mockup page map): the total and its delta, a per-month chart,
 * the next level as chart + table, top merchants, and the latest transactions with "See all". */
export function DetailPage({ detail, categories, filters, title, crumbs, childDimension, seeAllHref, defaultView = "monthly" }: Props) {
  const income = detail.type === "income";
  const good: Good = income ? "up" : "down";
  const context: BreakdownContext = { categories, slots: null, filters, good, type: detail.type };
  const rows = childDimension ? breakdownItems(detail.children, childDimension, context) : [];
  // A child's hint names its parent, which is this page's own scope: a category shows none
  // (mockup 03), a merchant only its count. The folded merchant row keeps its own.
  const children = rows.map((item) => {
    if (childDimension === "category") return { ...item, hint: "" };
    return item.key === "_other" ? item : { ...item, hint: plural(item.count, "transaction", "transactions") };
  });
  const merchants = breakdownItems(detail.top_merchants, "merchant", context);
  const names = new Map(children.map((item) => [item.key, item.name]));
  // The bars only stack by category, so the folded series reads like the table's folded row.
  const series = detail.child_keys.map((key, index) => ({
    key,
    label: key === "_other" ? "Other categories" : (names.get(key) ?? key),
    color: rampColor(key === "_other" ? 5 : index),
  }));
  const tiles = children
    .filter((item) => Number(item.amount) > 0)
    .map((item, index) => ({ name: item.name, value: Number(item.amount), share: item.share, fill: rampColor(index), href: item.href }));
  // Spec 2.6, Decision G: a period without data reads "—" with no delta, never €0. The API sends
  // zeros for it (a total and a line), so "has data" comes from the months.
  const hasData = periodHasData(detail.months, detail.period);
  const total = hasData ? Number(detail.total) : null;
  const cumulative = hasData ? detail.cumulative : { ...detail.cumulative, current: [] };
  const previous = detail.previous_total === null ? null : Number(detail.previous_total);
  const change = delta(total, previous, good, "euro");
  const versus = previousLabel(detail.period, "long");
  return (
    <>
      <Breadcrumb>
        <BreadcrumbList>
          {crumbs.map((crumb, index) => (
            <Fragment key={index}>
              {index > 0 && <BreadcrumbSeparator />}
              <BreadcrumbItem>
                {crumb.href ? (
                  <BreadcrumbLink render={<Link href={crumb.href} />}>{crumb.label}</BreadcrumbLink>
                ) : (
                  <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
                )}
              </BreadcrumbItem>
            </Fragment>
          ))}
        </BreadcrumbList>
      </Breadcrumb>
      <header className="flex flex-col gap-0.5">
        <h1 className="text-sm text-muted-foreground">
          {title} · {rangeLabel(detail.period)}
        </h1>
        {/* Spec 7.2: income is green with a "+"; expenses are neutral. */}
        <p className={cn("text-4xl font-semibold tracking-tight", income && total !== null && total > 0 && "text-income")}>
          {total === null ? <NoData /> : income ? signedMoney(total) : money(total)}
        </p>
        <p className="text-sm text-muted-foreground">
          {total === null ? (
            "No data in this period"
          ) : (
            <>
              <DeltaText value={change} /> <DeltaText value={delta(total, previous, good, "percent")} arrow={false} parens />{" "}
              {change.kind !== "hidden" && `${versus} · `}
              {plural(detail.count, "transaction", "transactions")}
            </>
          )}
        </p>
      </header>
      <SpendingCard
        name={title}
        months={detail.months}
        series={series}
        cumulative={cumulative}
        period={detail.period}
        split={childDimension === "category" && series.length > 1}
        defaultView={defaultView}
      />
      {childDimension && (
        <Card>
          <CardHeader>
            <CardTitle>{childDimension === "category" ? `Categories in ${title}` : `Merchants in ${title}`}</CardTitle>
            <CardDescription>
              {childDimension === "category"
                ? `Area = money ${detail.type === "expense" ? "spent" : "received"} · click a category to open it`
                : "Click a merchant to open it"}
            </CardDescription>
          </CardHeader>
          <CardContent className={cn("grid items-start gap-6", childDimension === "category" && "lg:grid-cols-2")}>
            {childDimension === "category" && <CategoryTreemap tiles={tiles} />}
            <BreakdownTable items={children} nameHeader={childDimension === "category" ? "Category" : "Merchant"} versus={versus} />
          </CardContent>
        </Card>
      )}
      <div className={cn("grid items-start gap-4", merchants.length > 0 && "lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]")}>
        {merchants.length > 0 && (
          <Card>
            {/* No link of its own: the Transactions card beside it opens the same list. */}
            <CardHeader>
              <CardTitle>Top merchants</CardTitle>
            </CardHeader>
            <CardContent>
              <BreakdownTable items={merchants} nameHeader="Merchant" versus={versus} showShare={false} />
            </CardContent>
          </Card>
        )}
        <Card>
          <CardHeader>
            <CardTitle>Transactions</CardTitle>
            {detail.count > 0 && (
              <CardAction>
                <Link href={seeAllHref} className="text-sm font-medium text-primary">
                  {detail.count === 1 ? "See it in Transactions" : `See all ${detail.count} in Transactions`}{" "}
                  <span aria-hidden>→</span>
                </Link>
              </CardAction>
            )}
          </CardHeader>
          <CardContent>
            {detail.latest.length > 0 ? (
              <TransactionTable items={detail.latest} />
            ) : (
              <p className="text-sm text-muted-foreground">No transactions in this period.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
