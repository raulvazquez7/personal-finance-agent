/** The skipped card keys kept in sessionStorage. Anything but an array of strings (a hand edit, an
 * older format) means nothing is skipped, so /review never fails on its own storage. */
export function parseSkipped(raw: string): string[] {
  try {
    const value: unknown = JSON.parse(raw);
    return Array.isArray(value) && value.every((key) => typeof key === "string") ? value : [];
  } catch {
    return [];
  }
}
