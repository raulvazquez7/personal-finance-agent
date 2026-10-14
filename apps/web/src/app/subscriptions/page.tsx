import type { Metadata } from "next";

import { Repeat } from "lucide-react";

import { SubscriptionTable } from "@/components/subscriptions/subscription-table";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { apiGet, type Schemas } from "@/lib/api";
import { money } from "@/lib/format";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Subscriptions" };

/** Active subscriptions and what they cost. Totals count the active list only. Ended rows sit below,
 * collapsed, and use the same table. */
export default async function SubscriptionsPage() {
  const { items, ended, monthly_total, yearly_total } = await apiGet<Schemas["Subscriptions"]>("/dashboard/subscriptions");
  return (
    <>
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold tracking-tight">Subscriptions</h1>
        <p className="max-w-prose text-sm text-muted-foreground">
          Charges you marked as subscriptions that are still running: charged within 45 days (monthly), 120 days (every
          3 months) or 400 days (yearly) of your latest imported transaction. The amount is the latest charge. A yearly
          subscription counts as a twelfth of that amount per month, and one every 3 months as a third. The yearly total
          is twelve times the monthly one. A subscription charged only once counts as monthly until its second charge.
          Subscriptions paid by credit card do not appear, because card statements are not imported.
        </p>
      </header>
      <section aria-label="Totals" className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Total label="Active" value={String(items.length)} />
        <Total label="Per month" value={money(monthly_total)} />
        <Total label="Per year" value={money(yearly_total)} />
      </section>
      {items.length === 0 ? (
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Repeat />
            </EmptyMedia>
            <EmptyTitle>No active subscriptions</EmptyTitle>
            <EmptyDescription>
              Mark a charge as a subscription in Transactions or Review, and it shows here with its cadence and cost.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <Card>
          <CardContent>
            <SubscriptionTable items={items} />
          </CardContent>
        </Card>
      )}
      {ended.length > 0 && (
        <details>
          <summary className="w-fit cursor-pointer text-sm font-medium">Ended ({ended.length})</summary>
          <div className="mt-3 flex flex-col gap-3">
            <p className="max-w-prose text-sm text-muted-foreground">
              These left the list because the last charge falls outside the cadence window. Changing the cadence can
              bring one back.
            </p>
            <Card>
              <CardContent>
                <SubscriptionTable items={ended} />
              </CardContent>
            </Card>
          </div>
        </details>
      )}
    </>
  );
}

function Total({ label, value }: { label: string; value: string }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription className="text-xs tracking-wide uppercase">{label}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold tracking-tight">{value}</p>
      </CardContent>
    </Card>
  );
}
