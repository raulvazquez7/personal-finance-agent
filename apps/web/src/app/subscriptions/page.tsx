import { Repeat } from "lucide-react";
import Link from "next/link";

import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet, type Schemas } from "@/lib/api";
import { dayLong, money } from "@/lib/format";

export const dynamic = "force-dynamic";

const CADENCE: Record<Schemas["SubscriptionOut"]["cadence"], string> = { monthly: "Monthly", yearly: "Yearly" };

/** Every active subscription with its amount, cadence, monthly equivalent and last charge, and
 * the monthly and yearly totals (spec 7.1). "Active" is relative to the latest import. */
export default async function SubscriptionsPage() {
  const { items, monthly_total, yearly_total } = await apiGet<Schemas["Subscriptions"]>("/dashboard/subscriptions");
  return (
    <>
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold tracking-tight">Subscriptions</h1>
        <p className="max-w-prose text-sm text-muted-foreground">
          Charges you marked as subscriptions that are still running: charged within 45 days (monthly) or 400 days
          (yearly) of your latest imported transaction. A yearly subscription counts as a twelfth of its typical amount
          per month, and the yearly total is twelve times the monthly one. A subscription charged only once counts as
          monthly until its second charge. Subscriptions paid by credit card do not appear, because card statements are
          not imported.
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
            {/* Below sm, Cadence and Amount are hidden so the table fits a phone without scrolling; long names
                wrap, and a yearly row says so under its name. */}
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Merchant</TableHead>
                  <TableHead className="hidden sm:table-cell">Cadence</TableHead>
                  <TableHead className="hidden text-right sm:table-cell">Amount</TableHead>
                  <TableHead className="text-right">Per month</TableHead>
                  <TableHead className="text-right">Last charge</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.merchant_id}>
                    <TableCell className="max-w-72 font-medium whitespace-normal wrap-anywhere">
                      <Link href={`/merchants/${item.merchant_id}`} className="hover:underline">
                        {item.merchant_name}
                      </Link>
                      {item.cadence === "yearly" && (
                        <p className="text-xs font-normal text-muted-foreground sm:hidden">{CADENCE.yearly}</p>
                      )}
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground sm:table-cell">{CADENCE[item.cadence]}</TableCell>
                    <TableCell className="hidden text-right sm:table-cell">{money(item.typical_amount)}</TableCell>
                    <TableCell className="text-right font-semibold">{money(item.monthly_equivalent)}</TableCell>
                    <TableCell className="text-right text-muted-foreground">{dayLong(item.last_charge)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
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
