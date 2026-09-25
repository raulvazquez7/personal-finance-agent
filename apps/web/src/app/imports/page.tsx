import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet, type Schemas } from "@/lib/api";

import { UploadForm } from "./upload-form";

export const dynamic = "force-dynamic";

export default async function ImportsPage() {
  const imports = await apiGet<Schemas["ImportRecord"][]>("/imports");

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader><CardTitle>Import statements</CardTitle></CardHeader>
        <CardContent><UploadForm /></CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Import history</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Account</TableHead>
                <TableHead>File</TableHead>
                <TableHead>Period</TableHead>
                <TableHead className="text-right">Rows</TableHead>
                <TableHead className="text-right">New</TableHead>
                <TableHead className="text-right">Duplicate</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {imports.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{new Date(row.imported_at).toLocaleString()}</TableCell>
                  <TableCell>{row.account_name}</TableCell>
                  <TableCell>{row.filename}</TableCell>
                  <TableCell>{row.period_start ?? "—"} → {row.period_end ?? "—"}</TableCell>
                  <TableCell className="text-right">{row.rows_total}</TableCell>
                  <TableCell className="text-right">{row.rows_new}</TableCell>
                  <TableCell className="text-right">{row.rows_duplicate}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
