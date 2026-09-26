"use client";

import { Check, ChevronDown } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { Schemas } from "@/lib/api";
import { accountDigits, accountsLabel } from "@/lib/labels";
import { parseFilters, replaceParams, toSearchParams } from "@/lib/params";

/** The account filter: none selected means all accounts; several can be picked (spec 6). */
export function AccountPicker({ accounts }: { accounts: Schemas["Account"][] }) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const selected = parseFilters(toSearchParams(search)).accounts;
  const go = (ids: string[]) => router.push(`${pathname}?${replaceParams(search.toString(), { account_id: ids })}`);
  const toggle = (id: string) => go(selected.includes(id) ? selected.filter((other) => other !== id) : [...selected, id]);
  const label = accountsLabel(selected, accounts);

  return (
    <Popover>
      <PopoverTrigger render={<Button variant="secondary" size="sm" className="rounded-full" />}>
        <span className="sr-only">Accounts: </span>
        {/* A renamed account can be 80 characters long: it must not push the top bar past a phone's width. */}
        <span className="max-w-40 truncate" title={label}>
          {label}
        </span>
        <ChevronDown data-icon="inline-end" />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-64 gap-0 p-1">
        <Button variant="ghost" className="justify-between" aria-pressed={selected.length === 0} onClick={() => go([])}>
          All accounts
          {selected.length === 0 && <Check data-icon="inline-end" />}
        </Button>
        {accounts.map((account) => {
          const digits = accountDigits(account);
          return (
            <Button
              key={account.id}
              variant="ghost"
              className="justify-between"
              aria-pressed={selected.includes(account.id)}
              onClick={() => toggle(account.id)}
            >
              <span className="truncate" title={account.name}>
                {account.name}
                {digits && <span className="text-muted-foreground"> {digits}</span>}
              </span>
              {selected.includes(account.id) && <Check data-icon="inline-end" />}
            </Button>
          );
        })}
      </PopoverContent>
    </Popover>
  );
}
