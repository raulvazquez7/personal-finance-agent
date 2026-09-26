import { FileUp } from "lucide-react";
import Link from "next/link";

import { CumulativeChart } from "@/components/charts/cumulative-chart";
import { MonthsChart } from "@/components/charts/months-chart";
import { DeltaText } from "@/components/money/delta-text";
import { KpiTile } from "@/components/money/kpi-tile";
import { WhereMoneyWent } from "@/components/overview/where-money-went";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { apiGet, type Schemas } from "@/lib/api";
import { breakdownItems, type BreakdownContext } from "@/lib/breakdown";
import { DEFINITIONS } from "@/lib/definitions";
import { atSameDay, delta, periodHasData } from "@/lib/delta";
import { money, moneyWhole, periodNames, previousLabel, rangeLabel, rate, signedMoneyWhole } from "@/lib/format";
import { plural } from "@/lib/labels";
import { filterParams, parseFilters, withFilters } from "@/lib/params";

export const dynamic = "force-dynamic";

const amount = (value: string | null | undefined) => (value === null || value === undefined ? null : Number(value));

/** "How am I doing?" in one look (spec 7.1; mockup 02). */
export default async function OverviewPage({ searchParams }: PageProps<"/">) {
  const filters = parseFilters(await searchParams);
  const [overview, categories] = await Promise.all([
    apiGet<Schemas["Overview"]>(`/dashboard/overview?${filterParams(filters)}`),
    apiGet<Schemas["CategoryOut"][]>("/categories"),
  ]);
  if (overview.period.latest_day === null) return <NoTransactions filtered={filters.accounts.length > 0} />;

  const { period, kpis, previous_kpis: before } = overview;
  const versus = previousLabel(period);
  // Decision G: a period without data shows "—" in the tiles, never €0. The API sends a line of
  // zeros for such a period, so its spending line is dropped too: no data, never 0 (spec 2.6).
  const hasData = periodHasData(overview.months, period);
  const cumulative = hasData ? overview.cumulative : { ...overview.cumulative, current: [] };
  const spent = atSameDay(cumulative);
  const context: BreakdownContext = { categories, slots: overview.group_slots, filters, good: "down", type: "expense" };
  const views = {
    // Every group with spend has its own row (spec 7.2). A group whose rows net to zero in the
    // period (a purchase and its refund) has nothing to show.
    group: breakdownItems(overview.by_group.filter((row) => Number(row.amount) !== 0), "group", context),
    category: breakdownItems(overview.by_category, "category", context),
    merchant: breakdownItems(overview.by_merchant, "merchant", context),
  };
  const subscriptions = overview.subscriptions;
  const expensesChange = delta(amount(kpis.expenses), amount(before?.expenses), "down", "percent");
  // "vs <previous>" only where a comparison shows (the donut and the table's change column).
  const compared = hasData && expensesChange.kind !== "hidden";
  return (
    <>
      <h1 className="sr-only">Overview, {rangeLabel(period)}</h1>
      <section aria-label="Key numbers" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiTile
          label="Income"
          definition={DEFINITIONS.income}
          value={signedMoneyWhole(kpis.income)}
          income
          hasData={hasData}
          delta={delta(amount(kpis.income), amount(before?.income), "up", "percent")}
          versus={versus}
          href={withFilters("/income", filters)}
        />
        <KpiTile
          label="Expenses"
          definition={DEFINITIONS.expenses}
          value={moneyWhole(kpis.expenses)}
          hasData={hasData}
          delta={expensesChange}
          versus={versus}
        />
        <KpiTile
          label="Savings"
          definition={DEFINITIONS.savings}
          value={moneyWhole(kpis.savings)}
          hasData={hasData}
          delta={delta(amount(kpis.savings), amount(before?.savings), "up", "euro")}
          versus={versus}
        />
        <KpiTile
          label="Savings rate"
          definition={DEFINITIONS.savingsRate}
          value={rate(kpis.savings_rate)}
          hasData={hasData}
          delta={delta(kpis.savings_rate, before?.savings_rate, "up", "points")}
          versus={versus}
        />
      </section>
      <Card>
        <CardHeader>
          <CardTitle>
            {/* An empty current series (no data in the period, or it starts after the latest imported day) is no data, never €0. */}
            {spent.current === null ? "No data" : `${moneyWhole(spent.current)} spent`}{" "}
            {period.name === "month" ? `in ${periodNames(period).current}` : "in this period"}
          </CardTitle>
          <CardDescription>
            <DeltaText value={delta(spent.current, spent.previous, "down", "euro")} />{" "}
            <DeltaText value={delta(spent.current, spent.previous, "down", "percent")} arrow={false} parens />{" "}
            {spent.previous !== null && `${previousLabel(period, "long")}${period.name === "month" ? " by the same day" : ""}`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CumulativeChart cumulative={cumulative} period={period} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Last 12 months</CardTitle>
          <CardDescription>Income, expenses and savings per month · months without imported data are marked</CardDescription>
        </CardHeader>
        <CardContent>
          <MonthsChart months={overview.months} range={[period.start.slice(0, 7), period.end.slice(0, 7)]} />
        </CardContent>
      </Card>
      <WhereMoneyWent
        views={views}
        total={hasData ? kpis.expenses : null}
        change={expensesChange}
        versus={versus}
        subtitle={`${rangeLabel(period)} · ${compared ? `${previousLabel(period, "long")} · ` : ""}colour = group`}
      />
      <Card size="sm">
        <CardHeader>
          <CardTitle>
            {plural(subscriptions.count, "active subscription", "active subscriptions")}
            {/* v_subscriptions is per merchant: the account filter does not apply, so say so. */}
            <span className="font-normal text-muted-foreground">
              {" "}
              · {money(subscriptions.monthly_total)} per month · {money(subscriptions.yearly_total)} per year · all
              accounts
            </span>
          </CardTitle>
          {/* Decision I: "active" is relative to the latest import (spec 5, v_subscriptions). */}
          <CardDescription>
            Active means charged within 45 days (monthly) or 400 days (yearly) of your latest imported transaction, not
            of today.
          </CardDescription>
          <CardAction>
            <Link href="/subscriptions" className="text-sm font-medium text-primary">
              Subscriptions →
            </Link>
          </CardAction>
        </CardHeader>
      </Card>
    </>
  );
}

/** Spec 7.2: with no imported data, the overview links to /imports. */
function NoTransactions({ filtered }: { filtered: boolean }) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <FileUp />
        </EmptyMedia>
        <EmptyTitle>{filtered ? "No transactions in these accounts" : "No statements yet"}</EmptyTitle>
        <EmptyDescription>Import a bank statement PDF to see your income, spending and savings here.</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button render={<Link href="/imports" />} nativeButton={false}>
          Import statements
        </Button>
      </EmptyContent>
    </Empty>
  );
}
