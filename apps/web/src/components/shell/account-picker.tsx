"use client";

import { Check, ChevronDown } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { Schemas } from "@/lib/api";
import { accountsLabel } from "@/lib/labels";
import { parseFilters, replaceParams, toSearchParams } from "@/lib/params";

/** The account filter: none selected means all accounts; several can be picked (spec 6). */
export function AccountPicker({ accounts }: { accounts: Schemas["Account"][] }) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const selected = parseFilters(toSearchParams(search)).accounts;
  const go = (ids: string[]) => router.push(`${pathname}?${replaceParams(search.toString(), { account_id: ids })}`);
  const toggle = (id: string) => go(selected.includes(id) ? selected.filter((other) => other !== id) : [...selected, id]);

  return (
    <Popover>
      <PopoverTrigger render={<Button variant="secondary" size="sm" className="rounded-full" />}>
        <span className="sr-only">Accounts: </span>
        {accountsLabel(selected, accounts)}
        <ChevronDown data-icon="inline-end" />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-64 gap-0 p-1">
        <Button variant="ghost" className="justify-between" aria-pressed={selected.length === 0} onClick={() => go([])}>
          All accounts
          {selected.length === 0 && <Check data-icon="inline-end" />}
        </Button>
        {accounts.map((account) => (
          <Button
            key={account.id}
            variant="ghost"
            className="justify-between"
            aria-pressed={selected.includes(account.id)}
            onClick={() => toggle(account.id)}
          >
            <span className="truncate">
              {account.name} <span className="text-muted-foreground">··{account.iban_last4}</span>
            </span>
            {selected.includes(account.id) && <Check data-icon="inline-end" />}
          </Button>
        ))}
      </PopoverContent>
    </Popover>
  );
}
