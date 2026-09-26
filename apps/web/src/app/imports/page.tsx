import type { Metadata } from "next";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NoData } from "@/components/money/no-data";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet, type Schemas } from "@/lib/api";
import { dateTime, dayRange } from "@/lib/format";

import { UploadForm } from "./upload-form";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Imports" };

export default async function ImportsPage() {
  const imports = await apiGet<Schemas["ImportRecord"][]>("/imports");

  return (
    <>
      <h1 className="text-xl font-semibold tracking-tight">Imports</h1>
      <Card>
        <CardHeader>
          <CardTitle>Import statements</CardTitle>
          <CardDescription>
            PDF statements from BBVA or CaixaBank. Each import starts a categorization run in the background.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <UploadForm />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Import history</CardTitle>
        </CardHeader>
        <CardContent>
          {imports.length === 0 ? (
            <p className="text-sm text-muted-foreground">No statements imported yet.</p>
          ) : (
            // On phones the table drops File and Rows (always New + Duplicate) and the text cells wrap,
            // so it fits the card at 390 px.
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>When</TableHead>
                  <TableHead>Account</TableHead>
                  <TableHead className="hidden sm:table-cell">File</TableHead>
                  <TableHead className="hidden md:table-cell">Period</TableHead>
                  <TableHead className="hidden text-right sm:table-cell">Rows</TableHead>
                  <TableHead className="text-right">New</TableHead>
                  <TableHead className="text-right">Duplicate</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {imports.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="whitespace-normal">{dateTime(row.imported_at)}</TableCell>
                    <TableCell className="whitespace-normal wrap-anywhere">{row.account_name}</TableCell>
                    {/* A long file name used to push the Duplicate column out of the card (issue 001). */}
                    <TableCell className="hidden max-w-48 truncate sm:table-cell" title={row.filename}>
                      {row.filename}
                    </TableCell>
                    <TableCell className="hidden whitespace-normal md:table-cell">
                      {row.period_start && row.period_end ? dayRange(row.period_start, row.period_end) : <NoData />}
                    </TableCell>
                    <TableCell className="hidden text-right sm:table-cell">{row.rows_total}</TableCell>
                    <TableCell className="text-right">{row.rows_new}</TableCell>
                    <TableCell className="text-right">{row.rows_duplicate}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </>
  );
}
