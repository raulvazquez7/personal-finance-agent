"use client";

import { useId } from "react";

import { Button } from "@/components/ui/button";
import type { Schemas } from "@/lib/api";

type Props = {
  item: Schemas["ReviewItem"];
  onYes: () => void;
  onNo: () => void;
  onSkip: () => void;
};

/** A possible duplicate (spec 9): Yes merges the card's merchant into the suggested one, No dismisses it. */
export function MergeCard({ item, onYes, onNo, onSkip }: Props) {
  const labelId = useId();
  return (
    <li>
      <div role="group" aria-labelledby={labelId} className="flex flex-wrap items-center gap-3 rounded-card bg-card p-4">
        <p id={labelId} className="min-w-0 text-sm break-words">
          Is <strong>{item.merchant?.name}</strong> the same merchant as <strong>{item.merge?.name}</strong>?
        </p>
        <div className="ml-auto flex gap-2">
          <Button variant="ghost" onClick={onSkip}>
            Skip
          </Button>
          <Button variant="outline" onClick={onNo}>
            No
          </Button>
          <Button onClick={onYes}>Yes</Button>
        </div>
      </div>
    </li>
  );
}
