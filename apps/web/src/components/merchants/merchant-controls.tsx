"use client";

import { useRouter } from "next/navigation";
import { useLayoutEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { CategoryPicker } from "@/components/pickers/category-picker";
import { CadenceSelect } from "@/components/subscriptions/cadence-select";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldContent, FieldDescription, FieldGroup, FieldLabel, FieldTitle } from "@/components/ui/field";
import { Switch } from "@/components/ui/switch";
import { ApiError, apiDelete, apiPost, type Schemas } from "@/lib/api";
import { plural } from "@/lib/labels";
import type { Direction } from "@/lib/pickers";

import { MerchantNameControls, type RunRequest } from "./merchant-name-controls";

type Props = {
  profile: Schemas["MerchantProfile"];
  categories: Schemas["CategoryOut"][];
  merchants: Schemas["MerchantOut"][];
  /** The page's money: spending pages pick expense categories, income pages income ones. */
  direction: Direction;
};

/** The merchant's controls (spec 7): its default category, subscription flag and cadence, then its
 * name and merge. Every change refreshes the page; a failure toasts the API's reason and keeps focus. */
export function MerchantControls({ profile, categories, merchants, direction }: Props) {
  const router = useRouter();
  const [categorySlug, setCategorySlug] = useState(profile.category_slug ?? "");
  const [subscription, setSubscription] = useState(profile.is_subscription === true);
  const [seen, setSeen] = useState(profile);
  const [pending, setPending] = useState(false);
  // The control that started the request: disabling it drops its focus, and a disabled button
  // ignores focus(), so it gets focus back once pending clears.
  const focusAfter = useRef<HTMLElement | null>(null);
  // A refresh brings the saved values.
  if (profile !== seen) {
    setSeen(profile);
    setCategorySlug(profile.category_slug ?? "");
    setSubscription(profile.is_subscription === true);
  }

  useLayoutEffect(() => {
    if (pending || !focusAfter.current) return;
    focusAfter.current.focus();
    focusAfter.current = null;
  }, [pending]);

  const current = categories.find((category) => category.slug === profile.category_slug);
  // Only money out is a subscription (spec 6): an income or transfer default has no switch to flip.
  const subscriptionAllowed = current?.tx_type === "expense";

  /** A failure toasts the API's reason. */
  const run: RunRequest = async (request, fallback, after) => {
    focusAfter.current = after ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null);
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
  };

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
    if (!cleared) return;
    // The button goes away with the default: focus moves to the picker, not back to the button.
    focusAfter.current = null;
    document.getElementById("merchant-category")?.focus();
    router.refresh();
  }

  async function saveSubscription(checked: boolean) {
    if (pending || !profile.category_slug || !subscriptionAllowed) return;
    setSubscription(checked);
    const body = { category_slug: profile.category_slug, is_subscription: checked };
    const saved = await run(() => apiPost(`/merchants/${profile.id}/review`, body), "Could not update the subscription flag.");
    if (saved) router.refresh();
    else setSubscription(profile.is_subscription === true);
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
          <Field orientation="horizontal" data-disabled={!subscriptionAllowed || undefined}>
            <Switch
              id="merchant-subscription"
              checked={subscription}
              disabled={!subscriptionAllowed || pending}
              onCheckedChange={saveSubscription}
              aria-describedby="merchant-subscription-help"
            />
            <FieldContent>
              <FieldLabel htmlFor="merchant-subscription">Subscription</FieldLabel>
              <FieldDescription id="merchant-subscription-help">
                {!profile.category_slug
                  ? "Set a default category first."
                  : subscriptionAllowed
                    ? "Applies to the transactions you or a rule did not label."
                    : "Only money out can be a subscription."}
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
        <MerchantNameControls profile={profile} merchants={merchants} pending={pending} run={run} />
      </CardContent>
    </Card>
  );
}
