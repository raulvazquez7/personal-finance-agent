import { Rectangle, useYAxisScale, type BarShapeProps } from "recharts";

import { monthShort } from "@/lib/format";

/** The first and last month (YYYY-MM) of the selected period. */
export type MonthRange = [string, string];

const inRange = (month: string, [from, to]: MonthRange) => month >= from && month <= to;

// The "no data" box stands on the €0 line. The € axis runs below zero when a month has negative
// savings, so the box follows the axis scale. Without a scale (no month has data) it stands on the
// axis line, `lift` px above the tick text.
const BOX = { width: 32, height: 30, lift: 12 };
// On a phone a month column is ~22 px: the box shrinks to its column, and a column under 28 px
// shows the month's first letter. The words are ~34 px wide, so they show only in a column of
// 40 px or more, which keeps neighbouring words apart (the <title> still says it on hover).
const NARROW = 28;
const WORDS = 40;

type TickProps = {
  x?: number | string;
  y?: number | string;
  width?: number | string; // the axis width, from Recharts
  visibleTicksCount?: number;
  payload?: { value?: string };
  range: MonthRange;
  noData: Set<string>;
};

/** The month under each column, bold inside the selected period, with a dashed "no data" box for
 * a month without imported data (spec 2.6: such a month is never drawn as zero). */
export function MonthTick({ x = 0, y = 0, width = Infinity, visibleTicksCount = 1, payload, range, noData }: TickProps) {
  const month = payload?.value ?? "";
  const cx = Number(x);
  const top = Number(y);
  const baseline = useYAxisScale()?.(0) ?? top - BOX.lift;
  const band = Number(width) / visibleTicksCount;
  const boxWidth = Math.min(BOX.width, band - 6);
  const name = month ? monthShort(month) : "";
  return (
    <g>
      {noData.has(month) && (
        <g>
          <title>no data</title>
          <rect
            x={cx - boxWidth / 2}
            y={baseline - BOX.height}
            width={boxWidth}
            height={BOX.height}
            rx={4}
            fill="transparent" // painted, so the whole box shows the <title> on hover
            stroke="var(--chart-previous)"
            strokeDasharray="3 3"
          />
          {band >= WORDS && (
            <text x={cx} y={baseline - BOX.height - 4} textAnchor="middle" fontSize={10} className="fill-muted-foreground">
              no data
            </text>
          )}
        </g>
      )}
      <text
        x={cx}
        y={top}
        dy="0.9em"
        textAnchor="middle"
        fontSize={12}
        className={inRange(month, range) ? "fill-foreground font-semibold" : "fill-muted-foreground"}
      >
        {band < NARROW ? name.charAt(0) : name}
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
