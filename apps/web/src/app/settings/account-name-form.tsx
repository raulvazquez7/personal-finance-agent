"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
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
    <form onSubmit={onSubmit}>
      <Field>
        <FieldLabel htmlFor={id} id={`${id}-label`}>
          {/* One string: Chrome drops a lone space between server-rendered text parts from the name. */}
          {`${account.bank.toUpperCase()} ${DIGITS_SEPARATOR}${account.iban_last4}`}
        </FieldLabel>
        <div className="flex gap-2">
          <Input
            id={id}
            value={name}
            maxLength={NAME_MAX}
            aria-describedby={`${id}-help`}
            onChange={(event) => setName(event.target.value)}
          />
          {/* "Save <account>": every account has a Save button. */}
          <Button
            type="submit"
            variant="outline"
            id={`${id}-save`}
            aria-labelledby={`${id}-save ${id}-label`}
            disabled={busy || !trimmed || trimmed === saved}
          >
            {busy && <Spinner data-icon="inline-start" />}
            Save
          </Button>
        </div>
        <FieldDescription id={`${id}-help`}>
          The name shown in lists and in the account filter, for example &quot;Joint account&quot;.
        </FieldDescription>
      </Field>
    </form>
  );
}
