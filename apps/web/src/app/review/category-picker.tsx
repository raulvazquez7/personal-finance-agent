"use client";

import {
  Combobox, ComboboxCollection, ComboboxContent, ComboboxEmpty, ComboboxGroup,
  ComboboxInput, ComboboxItem, ComboboxLabel, ComboboxList,
} from "@/components/ui/combobox";
import type { Schemas } from "@/lib/api";

type Category = Schemas["CategoryOut"];
type Group = { value: string; items: Category[] };

export const humanize = (slug: string) => slug.replaceAll("_", " ");

function byLevel1(categories: Category[]): Group[] {
  const groups = new Map<string, Category[]>();
  for (const category of categories) {
    groups.set(category.level1, [...(groups.get(category.level1) ?? []), category]);
  }
  return [...groups].map(([value, items]) => ({ value, items }));
}

type Props = {
  categories: Category[];
  suggested: Schemas["CategoryScore"][];
  value: string;
  onChange: (slug: string) => void;
};

export function CategoryPicker({ categories, suggested, value, onChange }: Props) {
  const bySlug = new Map(categories.map((c) => [c.slug, c]));
  const top = suggested.map((s) => bySlug.get(s.slug)).filter((c): c is Category => Boolean(c));
  const groups = [...(top.length ? [{ value: "suggested", items: top }] : []), ...byLevel1(categories)];

  return (
    <Combobox
      items={groups}
      value={bySlug.get(value) ?? null}
      onValueChange={(category: Category | null) => category && onChange(category.slug)}
      itemToStringLabel={(category: Category) => humanize(category.slug)}
    >
      <ComboboxInput placeholder="Category" className="w-full" />
      <ComboboxContent>
        <ComboboxEmpty>No category found.</ComboboxEmpty>
        <ComboboxList>
          {(group: Group) => (
            <ComboboxGroup key={group.value} items={group.items}>
              <ComboboxLabel>{humanize(group.value)}</ComboboxLabel>
              <ComboboxCollection>
                {(category: Category) => (
                  <ComboboxItem key={`${group.value}-${category.slug}`} value={category}>
                    {humanize(category.slug)}
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
