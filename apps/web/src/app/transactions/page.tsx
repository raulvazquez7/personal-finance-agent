import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet, euro, type Schemas } from "@/lib/api";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ month?: string }> };

export default async function TransactionsPage({ searchParams }: Props) {
  const { month } = await searchParams;
  const query = month ? `?month=${month}` : "";
  const transactions = await apiGet<Schemas["Transaction"][]>(`/transactions${query}`);

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <form method="get" className="flex items-center gap-2">
        <Input type="month" name="month" defaultValue={month} className="w-48" />
        <Button type="submit" variant="secondary">Filter</Button>
      </form>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Date</TableHead>
            <TableHead>Account</TableHead>
            <TableHead>Description</TableHead>
            <TableHead>Type</TableHead>
            <TableHead className="text-right">Amount</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {transactions.map((tx) => (
            <TableRow key={tx.id}>
              <TableCell>{tx.booked_at}</TableCell>
              <TableCell>{tx.account_name}</TableCell>
              <TableCell>{tx.merchant ?? tx.description_raw}</TableCell>
              <TableCell><Badge variant="outline">{tx.tx_type}</Badge></TableCell>
              <TableCell className={`text-right ${Number(tx.amount) < 0 ? "" : "text-green-700"}`}>
                {euro.format(Number(tx.amount))}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </main>
  );
}
