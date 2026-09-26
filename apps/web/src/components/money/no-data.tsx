/** The "—" of a period without data (spec 2.6, Decision G): screen readers say "No data", not
 * "em dash". */
export function NoData() {
  return (
    <>
      <span aria-hidden>—</span>
      <span className="sr-only">No data</span>
    </>
  );
}
