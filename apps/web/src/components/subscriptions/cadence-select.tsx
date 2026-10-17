"use client";

import { useRouter } from "next/navigation";
import { useLayoutEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ApiError, apiPatch } from "@/lib/api";

const CADENCE_LABEL = {
  monthly: "Monthly",
  quarterly: "Every 3 months",
  yearly: "Yearly",
} as const;

type Cadence = keyof typeof CADENCE_LABEL;
type Choice = "auto" | Cadence;

const OPTIONS: { value: Choice; label: string }[] = [
  { value: "auto", label: "Auto" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Every 3 months" },
  { value: "yearly", label: "Yearly" },
];

/** The cadence control for one merchant. Plan 2 imports this on the merchant page. */
export function CadenceSelect({
  merchantId,
  merchantName,
  cadence,
  source,
}: {
  merchantId: string;
  merchantName: string;
  cadence: Cadence | null;
  source: "auto" | "user";
}) {
  const router = useRouter();
  const triggerRef = useRef<HTMLButtonElement>(null);
  // Disabling the trigger while the request runs drops its focus, after a success as after a failure. Set
  // for every save and applied once pending clears: a disabled button ignores focus().
  const restoreFocus = useRef(false);
  // Auto while detection is in charge, or when nothing is detected yet. A user choice shows that value.
  const fromServer: Choice = source === "auto" || cadence === null ? "auto" : cadence;
  const [value, setValue] = useState(fromServer);
  const [seen, setSeen] = useState(fromServer);
  const [pending, setPending] = useState(false);
  if (fromServer !== seen) {
    setSeen(fromServer);
    setValue(fromServer);
  }

  useLayoutEffect(() => {
    if (pending || !restoreFocus.current) return;
    restoreFocus.current = false;
    triggerRef.current?.focus();
  }, [pending]);

  // The menu says "Auto". The trigger names the detected cadence, or plain "Auto" when there is none.
  const items = OPTIONS.map((option) =>
    option.value === "auto" && cadence !== null ? { ...option, label: `Auto · ${CADENCE_LABEL[cadence]}` } : option,
  );

  async function onValueChange(next: Choice | null) {
    if (next === null || next === value || pending) return;
    const previous = value;
    setValue(next);
    restoreFocus.current = true;
    setPending(true);
    try {
      await apiPatch(`/merchants/${merchantId}/cadence`, { cadence: next === "auto" ? null : next });
    } catch (error) {
      setValue(previous);
      toast.error(error instanceof ApiError && error.detail ? error.detail : "Could not update the cadence.");
      return;
    } finally {
      setPending(false);
    }
    router.refresh();
  }

  return (
    <Select items={items} value={value} onValueChange={onValueChange}>
      {/* One width for every row, sized for the longest label ("Auto · Every 3 months"), so the
          column does not zigzag. */}
      <SelectTrigger ref={triggerRef} disabled={pending} aria-label={`Cadence for ${merchantName}`} className="w-48">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}
