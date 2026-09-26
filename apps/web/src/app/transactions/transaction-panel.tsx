"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { CategoryPicker } from "@/components/pickers/category-picker";
import { MerchantPicker, type MerchantChoice } from "@/components/pickers/merchant-picker";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Field, FieldContent, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, apiDelete, apiPatch, apiPost, type Schemas } from "@/lib/api";
import { dayLong, signedMoney } from "@/lib/format";
import { label } from "@/lib/labels";
import type { Direction } from "@/lib/pickers";
import type { LabelChange } from "@/lib/transactions";
import { cn } from "@/lib/utils";

type Tx = Schemas["Transaction"];

type Props = {
  tx: Tx | null;
  categories: Schemas["CategoryOut"][];
  merchants: Schemas["MerchantOut"][];
  onClose: () => void;
  onSaved: (change: LabelChange) => void;
};

const NOTE_MAX = 500; // transactions.note: char_length(note) <= 500

/** The side panel (spec 7.3): the category, merchant, subscription flag and note of one row. */
export function TransactionPanel({ tx, categories, merchants, onClose, onSaved }: Props) {
  // Focus the panel itself on open, as Base UI does for touch: on a combobox that holds a value,
  // Escape clears the value and stops there, so a focused category box would keep Escape from
  // closing the panel. Tab still reaches the category first.
  const popup = useRef<HTMLDivElement>(null);
  return (
    <Sheet
      open={tx !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent ref={popup} initialFocus={popup} className="data-[side=right]:w-full data-[side=right]:sm:max-w-md">
        {tx && <PanelForm key={tx.id} tx={tx} categories={categories} merchants={merchants} onClose={onClose} onSaved={onSaved} />}
      </SheetContent>
    </Sheet>
  );
}

function PanelForm({ tx, categories, merchants, onClose, onSaved }: Omit<Props, "tx"> & { tx: Tx }) {
  const router = useRouter();
  const amount = Number(tx.amount);
  const direction: Direction = amount < 0 ? "out" : "in";
  const [categorySlug, setCategorySlug] = useState(tx.category_slug ?? "");
  const [merchant, setMerchant] = useState<MerchantChoice | null>(
    tx.merchant_id ? { id: tx.merchant_id, name: tx.merchant_name ?? "" } : null,
  );
  const [isSubscription, setIsSubscription] = useState(tx.is_subscription);
  const [note, setNote] = useState(tx.note ?? "");
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);

  const category = categories.find((c) => c.slug === categorySlug);
  const canSubscribe = direction === "out" && category?.tx_type === "expense";
  const merchantChanged = merchant !== null && (merchant.id === null || merchant.id !== tx.merchant_id);
  const labelChanged = categorySlug !== (tx.category_slug ?? "") || isSubscription !== tx.is_subscription || merchantChanged;
  const noteChanged = note.trim() !== (tx.note ?? "");
  const name = tx.merchant_name ?? tx.bank_merchant_text ?? tx.description_raw;

  function onSave() {
    // Only an existing merchant can take a default; a new name is created by this label alone.
    if (labelChanged && merchant?.id) setAsking(true);
    else void save(false);
  }

  async function save(toMerchant: boolean) {
    setBusy(true);
    try {
      const finalNote = note.trim() || null;
      const subscription = isSubscription && canSubscribe;
      // Money in has no subscription switch, so a default set from it gives no answer (null): the
      // merchant keeps its flag and every row its own mark. This row itself is never one.
      const defaultSubscription = direction === "in" ? null : subscription;
      if (noteChanged) await apiPatch(`/transactions/${tx.id}`, { note: finalNote });
      if (labelChanged) {
        await apiPost(`/transactions/${tx.id}/label`, {
          category_slug: categorySlug,
          is_subscription: subscription,
          merchant_id: merchant?.id ?? null,
          new_merchant_name: merchant && merchant.id === null ? merchant.name : null,
        });
      }
      if (toMerchant && merchant?.id) {
        // The merchant's default: its other rows (not the user's own labels) and future imports.
        await apiPost(`/merchants/${merchant.id}/review`, { category_slug: categorySlug, is_subscription: defaultSubscription });
      }
      onSaved({
        id: tx.id,
        categorySlug: labelChanged ? categorySlug : null,
        isSubscription: toMerchant ? defaultSubscription : subscription,
        merchant: merchantChanged ? merchant : null,
        note: finalNote,
        defaultFor: toMerchant && merchant?.id ? merchant.id : null,
      });
      toast.success(toMerchant && merchant ? `Saved for every ${merchant.name} transaction` : "Saved");
      router.refresh();
      onClose();
    } catch (error) {
      toast.error(error instanceof ApiError && error.detail ? error.detail : "Could not save this transaction.");
    } finally {
      setBusy(false);
      setAsking(false);
    }
  }

  async function clearDefault() {
    if (!tx.merchant_id) return;
    try {
      await apiDelete(`/merchants/${tx.merchant_id}/default`);
      toast.success(`${tx.merchant_name ?? "This merchant"} has no default category now.`);
    } catch {
      toast.error("Could not clear the merchant default.");
    }
  }

  return (
    <>
      <SheetHeader>
        {/* pr-8 keeps a long name clear of the close button in the corner. */}
        <SheetTitle className="pr-8 break-words">{name}</SheetTitle>
        <SheetDescription>
          {dayLong(tx.booked_at)} · {tx.account_name}
        </SheetDescription>
        <p className={cn("text-2xl font-semibold tracking-tight", amount > 0 && "text-income")}>{signedMoney(amount)}</p>
        <p className="text-xs break-words text-muted-foreground">{tx.description_raw}</p>
      </SheetHeader>
      <div className="flex-1 overflow-y-auto px-4">
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="panel-category">Category</FieldLabel>
            <CategoryPicker
              id="panel-category"
              categories={categories}
              direction={direction}
              value={categorySlug}
              onChange={setCategorySlug}
              ariaDescribedBy="panel-category-help"
            />
            <FieldDescription id="panel-category-help">
              {direction === "out" ? "What this money went on." : "Income, or the category of the purchase this money refunds."}
            </FieldDescription>
          </Field>
          <Field>
            <FieldLabel htmlFor="panel-merchant">Merchant</FieldLabel>
            <MerchantPicker
              id="panel-merchant"
              merchants={merchants}
              value={merchant}
              onChange={(choice) => choice && setMerchant(choice)}
              ariaDescribedBy="panel-merchant-help"
            />
            <FieldDescription id="panel-merchant-help">
              Who you paid or who paid you. Type a new name to create a merchant.
            </FieldDescription>
          </Field>
          <Field orientation="horizontal" data-disabled={!canSubscribe || undefined}>
            <Switch
              id="panel-subscription"
              checked={isSubscription && canSubscribe}
              disabled={!canSubscribe}
              onCheckedChange={(checked) => setIsSubscription(checked)}
              aria-describedby="panel-subscription-help"
            />
            <FieldContent>
              <FieldLabel htmlFor="panel-subscription">Subscription</FieldLabel>
              <FieldDescription id="panel-subscription-help">
                A charge that repeats, like a streaming plan. Only money going out can be one.
              </FieldDescription>
            </FieldContent>
          </Field>
          <Field>
            <FieldLabel htmlFor="panel-note">
              Note
              <span className="ml-auto font-normal text-muted-foreground">
                {note.length}/{NOTE_MAX}
              </span>
            </FieldLabel>
            <Textarea
              id="panel-note"
              value={note}
              maxLength={NOTE_MAX}
              onChange={(event) => setNote(event.target.value)}
              aria-describedby="panel-note-help"
            />
            <FieldDescription id="panel-note-help">
              What did you buy or what was it for? For example &apos;AirPods Pro&apos;. The AI uses it to answer your questions.
            </FieldDescription>
          </Field>
          {tx.merchant_id && (
            <Field>
              <Button
                variant="outline"
                size="sm"
                className="self-start"
                onClick={clearDefault}
                disabled={busy}
                aria-describedby="panel-clear-help"
              >
                Clear merchant default
              </Button>
              <FieldDescription id="panel-clear-help">
                For a merchant whose purchases need different categories: its transactions keep theirs, and new ones are
                categorized one by one.
              </FieldDescription>
            </Field>
          )}
        </FieldGroup>
      </div>
      <SheetFooter className="flex-row justify-end">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={onSave} disabled={busy || (!labelChanged && !noteChanged) || (labelChanged && !categorySlug)}>
          {busy && <Spinner data-icon="inline-start" />}
          Save
        </Button>
      </SheetFooter>
      <AlertDialog open={asking} onOpenChange={setAsking}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Apply to all transactions of this merchant?</AlertDialogTitle>
            <AlertDialogDescription>
              {merchant?.name} then uses {label(categorySlug)} for its other transactions and for new imports. Transactions you
              labelled yourself keep their category.
              {category?.tx_type === "income" && " Money going out keeps its category too: it is never income."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Back</AlertDialogCancel>
            <AlertDialogAction variant="outline" disabled={busy} onClick={() => save(false)}>
              Only this one
            </AlertDialogAction>
            <AlertDialogAction disabled={busy} onClick={() => save(true)}>
              Apply to all
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
