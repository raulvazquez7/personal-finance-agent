"use client";

import { useRouter } from "next/navigation";
import { Treemap } from "recharts";

import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { moneyWhole, percent } from "@/lib/format";

import { moneyRow } from "./money-tooltip";

export type Tile = { name: string; value: number; share: number; fill: string; href: string | null };

type TileProps = Partial<Tile> & {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  depth?: number;
  onOpen: (href: string) => void;
};

// Dark ink on ramp-3 to ramp-6, white on ramp-1 and ramp-2, for 12 px labels (Decision B: 4.5:1;
// ramp-2 is about 4.4:1 with either ink). Dataviz: a label inside a fill.
const LIGHT = new Set(["var(--ramp-3)", "var(--ramp-4)", "var(--ramp-5)", "var(--ramp-6)"]);

/** Recharts calls this for the root (depth 0) and for each tile (depth 1). A tile's label is left
 * out when its longer line would not fit, instead of being clipped (spec 8, gotcha 4). */
function TreemapTile({ x = 0, y = 0, width = 0, height = 0, depth, name = "", value = 0, share = 0, fill, href, onOpen }: TileProps) {
  if (depth !== 1) return <g />;
  const amount = `${moneyWhole(value)} · ${percent(share)}`;
  const fits = width > 20 + Math.max(name.length, amount.length) * 7 && height > 40;
  return (
    <g className={href ? "cursor-pointer" : undefined} onClick={() => href && onOpen(href)}>
      <rect x={x} y={y} width={width} height={height} rx={6} fill={fill} stroke="var(--card)" strokeWidth={3} />
      {fits && (
        <text x={x + 9} y={y + 18} fontSize={12} className={LIGHT.has(fill ?? "") ? "fill-foreground" : "fill-primary-foreground"}>
          <tspan fontWeight={600}>{name}</tspan>
          <tspan x={x + 9} dy={16}>
            {amount}
          </tspan>
        </text>
      )}
    </g>
  );
}

/** Categories in a group, area = money (mockup 03), in the same ramp shades as the stacked bars.
 * The table next to it is the accessible twin: tiles are for the mouse. */
export function CategoryTreemap({ tiles }: { tiles: Tile[] }) {
  const router = useRouter();
  if (tiles.length === 0) return null;
  return (
    <ChartContainer config={{}} className="aspect-auto h-52 w-full">
      <Treemap
        data={tiles}
        dataKey="value"
        nameKey="name"
        isAnimationActive={false}
        content={<TreemapTile onOpen={(href) => router.push(href)} />}
      >
        <ChartTooltip content={<ChartTooltipContent hideLabel formatter={moneyRow({})} />} />
      </Treemap>
    </ChartContainer>
  );
}
