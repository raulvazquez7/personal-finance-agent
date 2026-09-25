import { Rectangle, useYAxisScale, type BarShapeProps } from "recharts";

import { monthShort } from "@/lib/format";

/** The first and last month (YYYY-MM) of the selected period. */
export type MonthRange = [string, string];

const inRange = (month: string, [from, to]: MonthRange) => month >= from && month <= to;

// The "no data" box stands on the €0 line. The € axis runs below zero when a month has negative
// savings, so the box follows the axis scale. Without a scale (no month has data) it stands on the
// axis line, `lift` px above the tick text.
const BOX = { width: 32, height: 30, lift: 12 };

type TickProps = { x?: number | string; y?: number | string; payload?: { value?: string }; range: MonthRange; noData: Set<string> };

/** The month under each column, bold inside the selected period, with a dashed "no data" box for
 * a month without imported data (spec 2.6: such a month is never drawn as zero). */
export function MonthTick({ x = 0, y = 0, payload, range, noData }: TickProps) {
  const month = payload?.value ?? "";
  const cx = Number(x);
  const top = Number(y);
  const baseline = useYAxisScale()?.(0) ?? top - BOX.lift;
  return (
    <g>
      {noData.has(month) && (
        <>
          <rect
            x={cx - BOX.width / 2}
            y={baseline - BOX.height}
            width={BOX.width}
            height={BOX.height}
            rx={4}
            fill="none"
            stroke="var(--chart-previous)"
            strokeDasharray="3 3"
          />
          <text x={cx} y={baseline - BOX.height - 4} textAnchor="middle" fontSize={10} className="fill-muted-foreground">
            no data
          </text>
        </>
      )}
      <text
        x={cx}
        y={top}
        dy="0.9em"
        textAnchor="middle"
        fontSize={12}
        className={inRange(month, range) ? "fill-foreground font-semibold" : "fill-muted-foreground"}
      >
        {month ? monthShort(month) : ""}
      </text>
    </g>
  );
}

/** Columns outside the selected period are drawn lighter (mockup: the current month in full). */
export function monthBarShape(range: MonthRange) {
  return function MonthBar(props: BarShapeProps) {
    const month = (props.payload as { month?: string } | undefined)?.month ?? "";
    return <Rectangle {...props} fillOpacity={inRange(month, range) ? 1 : 0.55} />;
  };
}
