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
import { label } from "@/lib/labels";
import { pickerGroups, type Direction, type PickerGroup } from "@/lib/pickers";

type Category = Schemas["CategoryOut"];

type Props = {
  categories: Category[];
  direction: Direction;
  suggested?: string[];
  value: string;
  onChange: (slug: string) => void;
  id?: string;
  ariaLabel?: string;
  /** The id of the field's one-line description (spec 7.2). */
  ariaDescribedBy?: string;
};

/** A category picker that follows the money's direction (spec 7.3), used by /review, the
 * explorer's side panel and nothing else: the explorer's filter has its own (CategoryFilter). */
export function CategoryPicker({
  categories,
  direction,
  suggested = [],
  value,
  onChange,
  id,
  ariaLabel = "Category",
  ariaDescribedBy,
}: Props) {
  const bySlug = new Map(categories.map((category) => [category.slug, category]));
  return (
    <Combobox
      items={pickerGroups(categories, direction, suggested)}
      value={bySlug.get(value) ?? null}
      onValueChange={(category: Category | null) => category && onChange(category.slug)}
      // Escape on a closed picker empties it and stops there (Base UI), while the category stays
      // picked: keep the text (one `details` covers it and the value) and let Escape go on to the
      // panel around the picker.
      onInputValueChange={(_, details) => {
        if (details.reason === "escape-key") {
          details.cancel();
          details.allowPropagation();
        }
      }}
      itemToStringLabel={(category: Category) => label(category.slug)}
    >
      <ComboboxInput id={id} placeholder="Category" aria-label={ariaLabel} aria-describedby={ariaDescribedBy} className="w-full" />
      <ComboboxContent>
        <ComboboxEmpty>No category found.</ComboboxEmpty>
        <ComboboxList>
          {(group: PickerGroup) => (
            <ComboboxGroup key={group.value} items={group.items}>
              <ComboboxLabel>{group.label}</ComboboxLabel>
              <ComboboxCollection>
                {(category: Category) => (
                  <ComboboxItem key={`${group.value}-${category.slug}`} value={category}>
                    {label(category.slug)}
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
