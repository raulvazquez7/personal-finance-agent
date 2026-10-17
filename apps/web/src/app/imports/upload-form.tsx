"use client";

import { Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { type ChangeEvent, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { API_URL, type Schemas } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Drop or choose PDF statements; each one is imported as soon as it is picked (spec section 4.1).
 * The native file input covers the whole zone, so a click opens the picker and a drop lands on
 * the input, both without custom drag code. */
export function UploadForm() {
  const router = useRouter();
  const [messages, setMessages] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);

  async function onChange(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget; // React clears currentTarget once the handler awaits
    const files = [...(input.files ?? [])];
    setOver(false);
    if (files.length === 0) return;
    setBusy(true);
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
      input.value = ""; // the same file can be picked again
      setMessages(results);
      setBusy(false);
      router.refresh();
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        className={cn(
          "relative flex items-center gap-4 rounded-xl border-[1.5px] border-dashed border-input bg-background p-4 transition-colors has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-ring/50",
          over && "border-primary bg-accent",
          busy && "cursor-progress",
        )}
        // While busy the input is disabled, so a drop would reach the browser and open the PDF in this
        // tab. Idle, the input takes the drop natively, so nothing is cancelled then.
        onDragOver={(event) => {
          if (busy) event.preventDefault();
        }}
        onDrop={(event) => {
          if (busy) event.preventDefault();
        }}
      >
        {busy ? (
          <Spinner className="size-5 shrink-0 text-muted-foreground" />
        ) : (
          <Upload aria-hidden className="size-5 shrink-0 text-muted-foreground" />
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-sm font-medium">{busy ? "Importing…" : "Drop PDF statements here"}</span>
          <span id="statements-help" className="text-xs text-muted-foreground">
            or choose files · a statement imported twice only adds its new rows
          </span>
        </div>
        <span aria-hidden className={cn(buttonVariants({ variant: "outline", size: "sm" }), "shrink-0")}>
          Choose files
        </span>
        <input
          type="file"
          name="files"
          accept="application/pdf"
          multiple
          disabled={busy}
          aria-label="Statement PDFs"
          aria-describedby="statements-help"
          className="absolute inset-0 cursor-pointer opacity-0 disabled:pointer-events-none"
          onChange={onChange}
          onDragEnter={() => setOver(true)}
          onDragLeave={() => setOver(false)}
          onDrop={() => setOver(false)}
        />
      </div>
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
    </div>
  );
}
