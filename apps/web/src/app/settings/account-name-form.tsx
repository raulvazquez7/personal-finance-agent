"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { apiPatch, type Schemas } from "@/lib/api";
import { DIGITS_SEPARATOR } from "@/lib/labels";

const NAME_MAX = 80; // AccountUpdate.name: 1-80 characters

/** Rename one account (the existing PATCH /accounts/{id}, spec 7.1). */
export function AccountNameForm({ account }: { account: Schemas["Account"] }) {
  const router = useRouter();
  const [name, setName] = useState(account.name);
  const [saved, setSaved] = useState(account.name);
  const [busy, setBusy] = useState(false);
  const trimmed = name.trim();
  const id = `account-${account.id}`;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const updated = await apiPatch<Schemas["Account"]>(`/accounts/${account.id}`, { name: trimmed });
      setSaved(updated.name);
      setName(updated.name);
      toast.success("Account renamed");
      // The top bar's account picker reads the names in the root layout.
      router.refresh();
    } catch {
      toast.error("Could not rename the account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex items-start gap-3 border-t border-input py-3 first:border-t-0 first:pt-0 last:pb-0">
      {/* The bank's initial: a quiet marker, the label below names the bank. */}
      <span
        aria-hidden
        className="grid size-9 shrink-0 place-items-center rounded-full bg-background text-xs font-semibold ring-1 ring-input"
      >
        {account.bank.charAt(0).toUpperCase()}
      </span>
      <Field className="min-w-0 flex-1 gap-1">
        <Input
          id={id}
          value={name}
          maxLength={NAME_MAX}
          // Locked while saving, so the saved name cannot overwrite what is typed meanwhile. Read-only,
          // not disabled: a disabled field would drop the keyboard focus after Enter.
          readOnly={busy}
          onChange={(event) => setName(event.target.value)}
        />
        {/* Under the field, but still its label: the field keeps "BBVA ····1234" as its name. */}
        <FieldLabel htmlFor={id} id={`${id}-label`} className="text-xs font-normal text-muted-foreground">
          {/* One string: Chrome drops a lone space between server-rendered text parts from the name. */}
          {`${account.bank.toUpperCase()} ${DIGITS_SEPARATOR}${account.iban_last4}`}
        </FieldLabel>
      </Field>
      {/* "Save <account>": every account has a Save button. */}
      <Button
        type="submit"
        variant="outline"
        id={`${id}-save`}
        aria-labelledby={`${id}-save ${id}-label`}
        disabled={busy || !trimmed || trimmed === saved}
      >
        {busy && <Spinner data-icon="inline-start" />}
        {busy ? "Saving…" : "Save"}
      </Button>
    </form>
  );
}
