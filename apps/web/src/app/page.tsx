import { FileUp } from "lucide-react";
import Link from "next/link";

import { CumulativeChart } from "@/components/charts/cumulative-chart";
import { MonthsChart } from "@/components/charts/months-chart";
import { DeltaText } from "@/components/money/delta-text";
import { KpiTile } from "@/components/money/kpi-tile";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { apiGet, type Schemas } from "@/lib/api";
import { DEFINITIONS } from "@/lib/definitions";
import { atSameDay, delta, periodHasData } from "@/lib/delta";
import { moneyWhole, periodNames, previousLabel, rangeLabel, rate, signedMoneyWhole } from "@/lib/format";
import { filterParams, parseFilters, withFilters } from "@/lib/params";

export const dynamic = "force-dynamic";

const amount = (value: string | null | undefined) => (value === null || value === undefined ? null : Number(value));

/** "How am I doing?" in one look (spec 7.1; mockup 02). */
export default async function OverviewPage({ searchParams }: PageProps<"/">) {
  const filters = parseFilters(await searchParams);
  const overview = await apiGet<Schemas["Overview"]>(`/dashboard/overview?${filterParams(filters)}`);
  if (overview.period.latest_day === null) return <NoTransactions filtered={filters.accounts.length > 0} />;

  const { period, kpis, previous_kpis: before } = overview;
  const versus = previousLabel(period);
  const spent = atSameDay(overview.cumulative);
  // Decision G: a period without data shows "—" in the tiles, never €0.
  const hasData = periodHasData(overview.months, period);
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
          delta={delta(amount(kpis.expenses), amount(before?.expenses), "down", "percent")}
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
            {/* An empty current series (the period starts after the latest imported day) is no data, never €0. */}
            {spent.current === null ? "No data" : `${moneyWhole(spent.current)} spent`}{" "}
            {period.name === "month" ? `in ${periodNames(period).current}` : "in this period"}
          </CardTitle>
          <CardDescription>
            <DeltaText value={delta(spent.current, spent.previous, "down", "euro")} />{" "}
            <DeltaText value={delta(spent.current, spent.previous, "down", "percent")} arrow={false} parens />{" "}
            {spent.previous !== null && `${previousLabel(period, "long")} at the same day`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CumulativeChart cumulative={overview.cumulative} period={period} />
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
