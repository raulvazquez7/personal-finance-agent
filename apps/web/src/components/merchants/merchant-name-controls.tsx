"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";

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
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { apiPatch, type Schemas } from "@/lib/api";

/** Sends one merchant request; true when it succeeded. Focus goes back to `after` (by default the
 * control that started it) once the request settles. */
export type RunRequest = (request: () => Promise<void>, fallback: string, after?: HTMLElement | null) => Promise<boolean>;

type Props = {
  profile: Schemas["MerchantProfile"];
  merchants: Schemas["MerchantOut"][];
  pending: boolean;
  run: RunRequest;
};

/** The merchant's name and its merge into another one (spec 7): both can end on another page. */
export function MerchantNameControls({ profile, merchants, pending, run }: Props) {
  const router = useRouter();
  const search = useSearchParams();
  const [name, setName] = useState(profile.name);
  const [seenName, setSeenName] = useState(profile.name);
  const [mergeInto, setMergeInto] = useState<MerchantChoice | null>(null);
  const [confirming, setConfirming] = useState(false);
  const mergeButton = useRef<HTMLButtonElement>(null);
  // A refresh brings the saved name. A name being typed stays unless the name itself changed.
  if (profile.name !== seenName) {
    setSeenName(profile.name);
    setName(profile.name);
  }

  const others = merchants.filter((merchant) => merchant.id !== profile.id);
  const typedName = name.trim();

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
      if (id !== profile.id) toast.success("Merged into an existing merchant with that name.");
      open(id);
    }, "Could not rename this merchant.");
  }

  async function merge() {
    const target = mergeInto?.id;
    setConfirming(false);
    if (pending || !target) return;
    // The dialog's button goes away with it: a failure puts focus back on Merge.
    await run(async () => {
      const { id } = await apiPatch<Schemas["MerchantRef"]>(`/merchants/${profile.id}`, { merge_into_id: target });
      open(id);
    }, "Could not merge this merchant.", mergeButton.current);
  }

  return (
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
          <FieldDescription id="merchant-name-help">A name another merchant already has merges this one into it.</FieldDescription>
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
          <Button ref={mergeButton} variant="outline" onClick={() => setConfirming(true)} disabled={pending || !mergeInto?.id}>
            Merge
          </Button>
        </div>
      </Field>
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent finalFocus={mergeButton}>
          <AlertDialogHeader>
            <AlertDialogTitle>{`Merge ${profile.name} into ${mergeInto?.name}?`}</AlertDialogTitle>
            <AlertDialogDescription>
              {`Its transactions move to ${mergeInto?.name} and this page goes away. This cannot be undone.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={merge}>
              Merge
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </FieldGroup>
  );
}
