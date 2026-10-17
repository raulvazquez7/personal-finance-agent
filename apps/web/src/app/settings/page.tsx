import type { Metadata } from "next";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet, type Schemas } from "@/lib/api";

import { AccountNameForm } from "./account-name-form";
import { CategoryBrowser } from "./category-browser";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Settings" };

/** Rename accounts; the categories are read-only (spec 2026-10-17, section 6). */
export default async function SettingsPage() {
  const [accounts, categories, slots] = await Promise.all([
    apiGet<Schemas["Account"][]>("/accounts"),
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Record<string, number>>("/dashboard/group-slots"),
  ]);
  return (
    <>
      <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
      <Card>
        <CardHeader>
          <CardTitle>Accounts</CardTitle>
          <CardDescription>The name shown in lists and in the account filter, for example “Joint account”.</CardDescription>
        </CardHeader>
        <CardContent>
          {accounts.length === 0 ? (
            <p className="text-sm text-muted-foreground">No accounts yet: import a statement first.</p>
          ) : (
            <div className="flex flex-col">
              {accounts.map((account) => (
                <AccountNameForm key={account.id} account={account} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      <CategoryBrowser categories={categories} slots={slots} />
    </>
  );
}
