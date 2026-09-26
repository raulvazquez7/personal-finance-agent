"use client";

import { Search, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { CategoryFilter } from "@/components/pickers/category-filter";
import { MerchantPicker } from "@/components/pickers/merchant-picker";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Schemas } from "@/lib/api";
import { sourceLabel } from "@/lib/labels";
import { clearedExplorer, replaceParams, SOURCES, type ExplorerFilters as Explorer } from "@/lib/params";

type Props = { search: string; explorer: Explorer; categories: Schemas["CategoryOut"][]; merchants: Schemas["MerchantOut"][] };

const SUBSCRIPTION = [
  { value: null, label: "Any" },
  { value: "true", label: "Subscriptions only" },
  { value: "false", label: "Not subscriptions" },
];
const SOURCE = [{ value: null, label: "Any" }, ...SOURCES.map((value) => ({ value, label: sourceLabel(value) }))];

/** The explorer's filters (spec 7.3): search, type, group or category, merchant visible; the
 * account and period are in the top bar; subscription, source and needs review under "More
 * filters"; two saved filters. Each change rewrites the URL and the page refetches. */
export function ExplorerFilters({ search, explorer, categories, merchants }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const go = (changes: Record<string, string | undefined>) =>
    router.push(`${pathname}?${replaceParams(search, changes)}`, { scroll: false });
  // The switch shows only needs_review=true, so only that counts.
  const more = [explorer.is_subscription, explorer.category_source, explorer.needs_review === "true"].filter(Boolean).length;
  const merchant = merchants.find((m) => m.id === explorer.merchant_id);
  const cleared = clearedExplorer(search);
  // The box follows the URL ("Clear filters", Back) without remounting, so it keeps focus after Enter.
  const [q, setQ] = useState(explorer.q ?? "");
  const [urlQ, setUrlQ] = useState(explorer.q);
  if (explorer.q !== urlQ) {
    setUrlQ(explorer.q);
    setQ(explorer.q ?? "");
  }

  function onSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    go({ q: q.trim() || undefined });
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <form role="search" onSubmit={onSearch} className="w-full sm:w-72">
          <InputGroup>
            <InputGroupAddon>
              <Search />
            </InputGroupAddon>
            <InputGroupInput
              name="q"
              value={q}
              onChange={(event) => setQ(event.target.value)}
              maxLength={100}
              placeholder="Merchant, description or note"
              aria-label="Search transactions"
            />
          </InputGroup>
        </form>
        <ToggleGroup
          variant="segment"
          size="sm"
          aria-label="Type"
          value={[explorer.tx_type ?? "all"]}
          onValueChange={(value: string[]) => {
            if (!value[0]) return; // pressing the pressed item sends []: the type did not change
            go({ tx_type: value[0] !== "all" ? value[0] : undefined, level1: undefined, category: undefined });
          }}
        >
          <ToggleGroupItem value="all">All</ToggleGroupItem>
          <ToggleGroupItem value="expense">Expenses</ToggleGroupItem>
          <ToggleGroupItem value="income">Income</ToggleGroupItem>
          <ToggleGroupItem value="transfer">Transfers</ToggleGroupItem>
        </ToggleGroup>
        <CategoryFilter
          categories={categories}
          txType={explorer.tx_type}
          level1={explorer.level1}
          category={explorer.category}
          onChange={(level1, category) => go({ level1, category })}
        />
        <div className="w-full sm:w-56">
          <MerchantPicker
            merchants={merchants}
            value={merchant ? { id: merchant.id, name: merchant.name } : null}
            onChange={(choice) => go({ merchant_id: choice?.id ?? undefined })}
            allowCreate={false}
            showClear
            ariaLabel="Merchant filter"
          />
        </div>
        <Popover>
          <PopoverTrigger render={<Button variant="secondary" size="sm" />}>
            <SlidersHorizontal data-icon="inline-start" />
            More filters{more > 0 ? ` · ${more}` : ""}
          </PopoverTrigger>
          <PopoverContent align="start" className="w-72">
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="filter-subscription">Subscription</FieldLabel>
                <Select
                  items={SUBSCRIPTION}
                  value={explorer.is_subscription ?? null}
                  onValueChange={(value: string | null) => go({ is_subscription: value ?? undefined })}
                >
                  <SelectTrigger id="filter-subscription" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {SUBSCRIPTION.map((item) => (
                        <SelectItem key={item.label} value={item.value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
              <Field>
                <FieldLabel htmlFor="filter-source">Categorized by</FieldLabel>
                <Select
                  items={SOURCE}
                  value={explorer.category_source ?? null}
                  onValueChange={(value: string | null) => go({ category_source: value ?? undefined })}
                >
                  <SelectTrigger id="filter-source" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {SOURCE.map((item) => (
                        <SelectItem key={item.label} value={item.value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
              <Field orientation="horizontal">
                <Switch
                  id="filter-review"
                  checked={explorer.needs_review === "true"}
                  onCheckedChange={(checked) => go({ needs_review: checked ? "true" : undefined })}
                />
                <FieldLabel htmlFor="filter-review">Needs review only</FieldLabel>
              </Field>
            </FieldGroup>
          </PopoverContent>
        </Popover>
        {cleared !== search && (
          <Button variant="ghost" size="sm" render={<Link href={`${pathname}?${cleared}`} />} nativeButton={false}>
            Clear filters
          </Button>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span id="saved-filters">Saved filters</span>
        <ToggleGroup
          variant="segment"
          size="sm"
          aria-labelledby="saved-filters"
          value={explorer.saved ? [explorer.saved] : []}
          onValueChange={(value: string[]) => go({ saved: value[0] })}
        >
          <ToggleGroupItem value="unpaired_own">Own-account transfers without a pair</ToggleGroupItem>
          <ToggleGroupItem value="refunds">Refunds</ToggleGroupItem>
        </ToggleGroup>
      </div>
    </div>
  );
}
