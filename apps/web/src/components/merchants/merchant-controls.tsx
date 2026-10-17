"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { CategoryPicker } from "@/components/pickers/category-picker";
import { MerchantPicker, type MerchantChoice } from "@/components/pickers/merchant-picker";
import { CadenceSelect } from "@/components/subscriptions/cadence-select";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldContent, FieldDescription, FieldGroup, FieldLabel, FieldTitle } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { ApiError, apiDelete, apiPatch, apiPost, type Schemas } from "@/lib/api";
import { plural } from "@/lib/labels";
import type { Direction } from "@/lib/pickers";

type Props = {
  profile: Schemas["MerchantProfile"];
  categories: Schemas["CategoryOut"][];
  merchants: Schemas["MerchantOut"][];
  /** The page's money: spending pages pick expense categories, income pages income ones. */
  direction: Direction;
};

/** The merchant's controls (spec 7): its default category, subscription flag, cadence, name and
 * merge. Every change refreshes the page; a failure toasts the API's reason and keeps focus. */
export function MerchantControls({ profile, categories, merchants, direction }: Props) {
  const router = useRouter();
  const search = useSearchParams();
  const [categorySlug, setCategorySlug] = useState(profile.category_slug ?? "");
  const [subscription, setSubscription] = useState(profile.is_subscription === true);
  const [name, setName] = useState(profile.name);
  const [mergeInto, setMergeInto] = useState<MerchantChoice | null>(null);
  const [seen, setSeen] = useState(profile);
  const [pending, setPending] = useState(false);
  // The control that started the request: disabling it drops its focus, and a disabled button
  // ignores focus(), so it gets focus back once pending clears.
  const focusAfter = useRef<HTMLElement | null>(null);
  // A refresh brings the saved values. A name being typed stays unless the name itself changed.
  if (profile !== seen) {
    setSeen(profile);
    setCategorySlug(profile.category_slug ?? "");
    setSubscription(profile.is_subscription === true);
    if (profile.name !== seen.name) setName(profile.name);
  }

  useLayoutEffect(() => {
    if (pending || !focusAfter.current) return;
    focusAfter.current.focus();
    focusAfter.current = null;
  }, [pending]);

  const current = categories.find((category) => category.slug === profile.category_slug);
  const others = merchants.filter((merchant) => merchant.id !== profile.id);
  const typedName = name.trim();

  /** True when the request succeeded; a failure toasts the API's reason. */
  async function run(request: () => Promise<void>, fallback: string): Promise<boolean> {
    focusAfter.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setPending(true);
    try {
      await request();
      return true;
    } catch (error) {
      toast.error(error instanceof ApiError && error.detail ? error.detail : fallback);
      return false;
    } finally {
      setPending(false);
    }
  }

  async function saveCategory(slug: string) {
    if (pending || slug === profile.category_slug) return;
    setCategorySlug(slug);
    const body = { category_slug: slug, is_subscription: profile.is_subscription };
    const saved = await run(() => apiPost(`/merchants/${profile.id}/review`, body), "Could not set the default category.");
    if (saved) router.refresh();
    else setCategorySlug(profile.category_slug ?? "");
  }

  async function clearDefault() {
    if (pending) return;
    const cleared = await run(() => apiDelete(`/merchants/${profile.id}/default`), "Could not clear the default category.");
    if (cleared) router.refresh();
  }

  async function saveSubscription(checked: boolean) {
    if (pending || !profile.category_slug) return;
    setSubscription(checked);
    const body = { category_slug: profile.category_slug, is_subscription: checked };
    const saved = await run(() => apiPost(`/merchants/${profile.id}/review`, body), "Could not update the subscription flag.");
    if (saved) router.refresh();
    else setSubscription(profile.is_subscription === true);
  }

  /** The survivor of a rename or merge: another merchant opens with the same period and filters. */
  function open(id: string) {
    if (id === profile.id) router.refresh();
    else router.push(`/merchants/${id}?${search.toString()}`);
  }

  async function rename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !typedName || typedName === profile.name) return;
    await run(async () => {
      const { id } = await apiPatch<Schemas["MerchantRef"]>(`/merchants/${profile.id}`, { name: typedName });
      // A name another merchant already has merges into it.
      if (id !== profile.id) toast.success(`Merged into the merchant named ${typedName}.`);
      open(id);
    }, "Could not rename this merchant.");
  }

  async function merge() {
    const target = mergeInto?.id;
    if (pending || !target) return;
    await run(async () => {
      const { id } = await apiPatch<Schemas["MerchantRef"]>(`/merchants/${profile.id}`, { merge_into_id: target });
      open(id);
    }, "Could not merge this merchant.");
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Merchant settings</CardTitle>
      </CardHeader>
      <CardContent className="grid items-start gap-6 md:grid-cols-2">
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="merchant-category">Default category</FieldLabel>
            <p className="text-sm font-medium">{current ? `${current.group_name} › ${current.name}` : "No default"}</p>
            <CategoryPicker
              id="merchant-category"
              categories={categories}
              direction={direction}
              value={categorySlug}
              onChange={saveCategory}
              ariaLabel="Default category"
              ariaDescribedBy="merchant-category-help"
            />
            <FieldDescription id="merchant-category-help">
              Would change up to {plural(profile.rows_a_default_would_change, "transaction", "transactions")}. Ones you or a
              rule labelled stay, and money out never becomes income.
            </FieldDescription>
            {profile.category_slug && (
              <>
                {/* A field stretches its children; the wrapper keeps the button its own width. */}
                <div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={clearDefault}
                    disabled={pending}
                    aria-describedby="merchant-clear-help"
                  >
                    Clear default
                  </Button>
                </div>
                <FieldDescription id="merchant-clear-help">
                  Clearing also clears the subscription flag. The transactions keep their categories, and new ones are
                  categorized one by one.
                </FieldDescription>
              </>
            )}
          </Field>
          <Field orientation="horizontal" data-disabled={!profile.category_slug || undefined}>
            <Switch
              id="merchant-subscription"
              checked={subscription}
              disabled={!profile.category_slug || pending}
              onCheckedChange={saveSubscription}
              aria-describedby="merchant-subscription-help"
            />
            <FieldContent>
              <FieldLabel htmlFor="merchant-subscription">Subscription</FieldLabel>
              <FieldDescription id="merchant-subscription-help">
                {profile.category_slug
                  ? "Applies to the transactions you or a rule did not label."
                  : "Set a default category first."}
              </FieldDescription>
            </FieldContent>
          </Field>
          <Field>
            {/* The select names itself ("Cadence for …"), so this title is not a <label>. */}
            <FieldTitle>Cadence</FieldTitle>
            {/* A stored cadence is the user's; otherwise the detected one, null without flagged charges. */}
            <div>
              <CadenceSelect
                merchantId={profile.id}
                merchantName={profile.name}
                cadence={profile.cadence ?? profile.cadence_effective}
                source={profile.cadence !== null ? "user" : "auto"}
              />
            </div>
          </Field>
        </FieldGroup>
        <FieldGroup>
          <form onSubmit={rename}>
            <Field>
              <FieldLabel htmlFor="merchant-name">Name</FieldLabel>
              <div className="flex gap-2">
                <Input
                  id="merchant-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  aria-describedby="merchant-name-help"
                />
                <Button type="submit" disabled={pending || !typedName || typedName === profile.name}>
                  Save
                </Button>
              </div>
              <FieldDescription id="merchant-name-help">
                A name another merchant already has merges this one into it.
              </FieldDescription>
            </Field>
          </form>
          <Field>
            <FieldLabel htmlFor="merchant-merge">Merge into</FieldLabel>
            {/* Above the field: from sm the picker's "Showing 50 of N" hint hangs under it. */}
            <FieldDescription id="merchant-merge-help">
              Moves every transaction to the merchant you pick, and this merchant is gone.
            </FieldDescription>
            <div className="flex gap-2">
              <div className="relative min-w-0 flex-1">
                <MerchantPicker
                  id="merchant-merge"
                  merchants={others}
                  value={mergeInto}
                  onChange={setMergeInto}
                  allowCreate={false}
                  ariaLabel="Merge into"
                  ariaDescribedBy="merchant-merge-help"
                />
              </div>
              <Button variant="outline" onClick={merge} disabled={pending || !mergeInto?.id}>
                Merge
              </Button>
            </div>
          </Field>
        </FieldGroup>
      </CardContent>
    </Card>
  );
}
