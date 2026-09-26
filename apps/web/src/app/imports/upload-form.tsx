"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { API_URL, type Schemas } from "@/lib/api";

export function UploadForm() {
  const router = useRouter();
  const [messages, setMessages] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const files = new FormData(event.currentTarget).getAll("files") as File[];
    const results: string[] = [];
    try {
      for (const file of files) {
        try {
          const body = new FormData();
          body.append("file", file);
          const response = await fetch(`${API_URL}/imports`, { method: "POST", body });
          if (response.ok) {
            const summary = (await response.json()) as Schemas["ImportSummary"];
            results.push(`${file.name}: ${summary.rows_new} new, ${summary.rows_duplicate} duplicate`);
          } else {
            const text = await response.text();
            let detail: unknown;
            try {
              detail = JSON.parse(text).detail;
            } catch {
              detail = undefined;
            }
            results.push(
              typeof detail === "string" ? `${file.name}: ${detail}` : `${file.name}: ${response.status} ${text}`,
            );
          }
        } catch (error) {
          results.push(`${file.name}: ${error instanceof Error ? error.message : String(error)}`);
        }
      }
    } finally {
      setMessages(results);
      setBusy(false);
      router.refresh();
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <Field>
        <FieldLabel htmlFor="statements">Statement PDFs</FieldLabel>
        <div className="flex items-center gap-2">
          <Input
            id="statements"
            type="file"
            name="files"
            accept="application/pdf"
            multiple
            required
            aria-describedby="statements-help"
          />
          <Button type="submit" disabled={busy}>
            {busy && <Spinner data-icon="inline-start" />}
            {busy ? "Importing…" : "Import"}
          </Button>
        </div>
        <FieldDescription id="statements-help">
          One or more PDF statements. A statement imported twice only adds its new rows.
        </FieldDescription>
      </Field>
      <div aria-live="polite">
        {messages.length > 0 && (
          // A long file name without spaces wraps instead of running past the card on a phone.
          <ul className="text-sm wrap-anywhere text-muted-foreground">
            {/* By position: two picked files with the same name and outcome give the same message. The
                list is replaced whole on each import, never reordered. */}
            {messages.map((message, index) => (
              <li key={index}>{message}</li>
            ))}
          </ul>
        )}
      </div>
    </form>
  );
}
