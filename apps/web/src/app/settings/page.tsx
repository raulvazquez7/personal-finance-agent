import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FieldGroup } from "@/components/ui/field";
import { apiGet, type Schemas } from "@/lib/api";
import { label } from "@/lib/labels";
import { byLevel1 } from "@/lib/pickers";

import { AccountNameForm } from "./account-name-form";

export const dynamic = "force-dynamic";

const TYPES = [
  { type: "expense", title: "Expenses" },
  { type: "income", title: "Income" },
  { type: "transfer", title: "Transfers (out of every total)" },
] as const;

/** Rename accounts; the categories are read-only in slice 3 (spec 7.1). */
export default async function SettingsPage() {
  const [accounts, categories] = await Promise.all([
    apiGet<Schemas["Account"][]>("/accounts"),
    apiGet<Schemas["CategoryOut"][]>("/categories"),
  ]);
  return (
    <>
      <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
      <Card>
        <CardHeader>
          <CardTitle>Accounts</CardTitle>
          <CardDescription>Give each account a name you recognize.</CardDescription>
        </CardHeader>
        <CardContent>
          {accounts.length === 0 ? (
            <p className="text-sm text-muted-foreground">No accounts yet: import a statement first.</p>
          ) : (
            <FieldGroup>
              {accounts.map((account) => (
                <AccountNameForm key={account.id} account={account} />
              ))}
            </FieldGroup>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Categories</CardTitle>
          <CardDescription>
            Read-only in this version. A refund takes the category of its purchase; transfers never count as income or
            spending.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          {TYPES.map(({ type, title }) => (
            <section key={type} className="flex flex-col gap-3">
              <h2 className="text-sm font-medium">{title}</h2>
              <dl className="grid gap-4 sm:grid-cols-2">
                {byLevel1(categories.filter((category) => category.tx_type === type)).map((group) => (
                  <div key={group.value} className="flex flex-col gap-1.5">
                    <dt className="text-xs tracking-wide text-muted-foreground uppercase">{group.label}</dt>
                    <dd className="flex flex-wrap gap-1">
                      {group.items.map((category) => (
                        <Badge key={category.slug} variant="outline">
                          {label(category.slug)}
                        </Badge>
                      ))}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </CardContent>
      </Card>
    </>
  );
}
