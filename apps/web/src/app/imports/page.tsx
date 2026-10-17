import type { Metadata } from "next";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet, type Schemas } from "@/lib/api";
import { accountDigits } from "@/lib/labels";

import { CoverageBoard } from "./coverage-board";
import { ImportHistory } from "./import-history";
import { UploadForm } from "./upload-form";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Imports" };

export default async function ImportsPage() {
  const [imports, accounts] = await Promise.all([
    apiGet<Schemas["ImportRecord"][]>("/imports"),
    apiGet<Schemas["Account"][]>("/accounts"),
  ]);
  // The server's own calendar day (spec section 2, Today). en-CA writes YYYY-MM-DD.
  const today = new Date().toLocaleDateString("en-CA");

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
      {imports.length > 0 && (
        <CoverageBoard
          today={today}
          accounts={accounts.map((account) => ({ id: account.id, name: account.name, digits: accountDigits(account) }))}
          imports={imports.map((row) => ({ accountId: row.account_id, start: row.period_start, end: row.period_end }))}
        />
      )}
      <ImportHistory imports={imports} />
    </>
  );
}
