"use client";

import {
  Combobox,
  ComboboxCollection,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxGroup,
  ComboboxInput,
  ComboboxItem,
  ComboboxLabel,
  ComboboxList,
} from "@/components/ui/combobox";
import type { Schemas } from "@/lib/api";
import type { TxType } from "@/lib/params";
import { filterGroups, type FilterGroup, type FilterOption } from "@/lib/pickers";

type Props = {
  categories: Schemas["CategoryOut"][];
  txType?: TxType;
  level1?: string;
  category?: string;
  onChange: (level1: string | undefined, category: string | undefined) => void;
};

/** "Group or category" in one picker (spec 7.3), following the type filter. */
export function CategoryFilter({ categories, txType, level1, category, onChange }: Props) {
  const groups = filterGroups(categories, txType);
  const value =
    groups
      .flatMap((group) => group.items)
      .find((option) =>
        category ? option.kind === "category" && option.value === category : option.kind === "group" && option.value === level1,
      ) ?? null;
  return (
    <Combobox
      items={groups}
      value={value}
      onValueChange={(option: FilterOption | null) =>
        onChange(option?.kind === "group" ? option.value : undefined, option?.kind === "category" ? option.value : undefined)
      }
      itemToStringLabel={(option: FilterOption) => option.label}
      isItemEqualToValue={(a: FilterOption, b: FilterOption) => a.kind === b.kind && a.value === b.value}
    >
      <ComboboxInput placeholder="Group or category" aria-label="Group or category filter" showClear className="w-full sm:w-56" />
      <ComboboxContent>
        <ComboboxEmpty>No category found.</ComboboxEmpty>
        <ComboboxList>
          {(group: FilterGroup) => (
            <ComboboxGroup key={group.value} items={group.items}>
              <ComboboxLabel>{group.label}</ComboboxLabel>
              <ComboboxCollection>
                {(option: FilterOption) => (
                  <ComboboxItem key={`${option.kind}-${option.value}`} value={option}>
                    {option.label}
                  </ComboboxItem>
                )}
              </ComboboxCollection>
            </ComboboxGroup>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
