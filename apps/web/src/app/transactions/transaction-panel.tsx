"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
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
  return (
    <Sheet
      open={tx !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent className="data-[side=right]:w-full data-[side=right]:sm:max-w-md">
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
  const [confirmingClear, setConfirmingClear] = useState(false);
  // The request running, if any: its button says so, and every button waits for it.
  const [pending, setPending] = useState<"save" | "clear" | null>(null);
  const busy = pending !== null;

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
    setPending("save");
    try {
      const finalNote = note.trim() || null;
      const subscription = isSubscription && canSubscribe;
      // Money in has no subscription switch, so a default set from it gives no answer (null): the
      // merchant keeps its flag and every row its own mark. This row itself is never one.
      const defaultSubscription = direction === "in" ? null : subscription;
      // The label first: when the API refuses it (a 422), the note is not saved either.
      if (labelChanged) {
        await apiPost(`/transactions/${tx.id}/label`, {
          category_slug: categorySlug,
          is_subscription: subscription,
          merchant_id: merchant?.id ?? null,
          new_merchant_name: merchant && merchant.id === null ? merchant.name : null,
        });
      }
      if (noteChanged) await apiPatch(`/transactions/${tx.id}`, { note: finalNote });
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
      // Not "every transaction": rows you or a rule labelled keep theirs, as the dialog says.
      toast.success(toMerchant && merchant ? `${merchant.name} now uses ${label(categorySlug)}` : "Saved");
      router.refresh();
      onClose();
    } catch (error) {
      toast.error(error instanceof ApiError && error.detail ? error.detail : "Could not save this transaction.");
    } finally {
      setPending(null);
      setAsking(false);
    }
  }

  async function clearDefault() {
    if (!tx.merchant_id) return;
    // Busy until the answer, so a double click sends one DELETE.
    setPending("clear");
    try {
      await apiDelete(`/merchants/${tx.merchant_id}/default`);
      toast.success(`${tx.merchant_name ?? "This merchant"} has no default category now.`);
    } catch {
      toast.error("Could not clear the merchant default.");
    } finally {
      setPending(null);
      setConfirmingClear(false);
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
              <span aria-hidden className="ml-auto font-normal text-muted-foreground">
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
              What did you buy or what was it for? For example ‘AirPods Pro’. The AI uses it to answer your questions.
            </FieldDescription>
          </Field>
          {tx.merchant_id && (
            <Field>
              <Button
                variant="outline"
                size="sm"
                className="self-start"
                onClick={() => setConfirmingClear(true)}
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
          {pending === "save" && <Spinner data-icon="inline-start" />}
          {pending === "save" ? "Saving…" : "Save"}
        </Button>
      </SheetFooter>
      <AlertDialog open={asking} onOpenChange={setAsking}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Apply to all transactions of this merchant?</AlertDialogTitle>
            <AlertDialogDescription>
              {merchant?.name} then uses {label(categorySlug)} for its other transactions and for new imports. Transactions
              that you or a rule labelled keep their category.
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
      {/* Confirmed first, not undone: the panel does not know the default it would restore. */}
      <AlertDialog open={confirmingClear} onOpenChange={setConfirmingClear}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{`Clear the default category of ${tx.merchant_name ?? "this merchant"}?`}</AlertDialogTitle>
            <AlertDialogDescription>
              Its transactions keep their categories, and new ones are categorized one by one.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Back</AlertDialogCancel>
            <AlertDialogAction disabled={busy} onClick={clearDefault}>
              {pending === "clear" && <Spinner data-icon="inline-start" />}
              {pending === "clear" ? "Clearing…" : "Clear default"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
