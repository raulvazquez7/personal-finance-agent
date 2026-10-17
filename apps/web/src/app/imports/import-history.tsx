import { NoData } from "@/components/money/no-data";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Schemas } from "@/lib/api";
import { dateTime, dayRange, monthLabel } from "@/lib/format";
import { groupByEndMonth } from "@/lib/import-history";

/** Every import, one section per month in which a statement ends (spec section 4.3). The file
 * name stays in the API and is not shown. */
export function ImportHistory({ imports }: { imports: Schemas["ImportRecord"][] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Import history</CardTitle>
      </CardHeader>
      <CardContent>
        {imports.length === 0 ? (
          <p className="text-sm text-muted-foreground">No statements imported yet.</p>
        ) : (
          // On phones the table drops Imported and Rows, and the text cells wrap.
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Period</TableHead>
                <TableHead>Account</TableHead>
                <TableHead className="hidden sm:table-cell">Imported</TableHead>
                <TableHead className="hidden text-right md:table-cell">Rows</TableHead>
                <TableHead className="text-right">New</TableHead>
                <TableHead className="text-right">Duplicate</TableHead>
              </TableRow>
            </TableHeader>
            {groupByEndMonth(imports).map((group) => (
              <TableBody key={group.month ?? "none"}>
                <TableRow className="hover:bg-transparent">
                  <TableHead scope="rowgroup" colSpan={6} className="h-auto pt-4 pb-1 tracking-normal normal-case">
                    {group.month ? monthLabel(group.month) : "No period"}
                  </TableHead>
                </TableRow>
                {group.rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="whitespace-normal">
                      {row.period_start && row.period_end ? dayRange(row.period_start, row.period_end) : <NoData />}
                    </TableCell>
                    <TableCell className="whitespace-normal wrap-anywhere">{row.account_name}</TableCell>
                    <TableCell className="hidden whitespace-normal text-muted-foreground sm:table-cell">
                      {dateTime(row.imported_at)}
                    </TableCell>
                    <TableCell className="hidden text-right md:table-cell">{row.rows_total}</TableCell>
                    <TableCell className="text-right">{row.rows_new}</TableCell>
                    <TableCell className="text-right">{row.rows_duplicate}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            ))}
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
