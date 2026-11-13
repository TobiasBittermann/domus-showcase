import type { StoreSlice } from '../../api/queries'
import type { Slice } from './DonutChart'

/** Categorical slots (validated light + dark), defined as CSS variables in index.css. */
const SLOTS = 6
export const OTHER_COLOR = 'var(--series-other)'

/**
 * Color follows the store, not its rank in one chart: both charts share one map.
 * The stores shopped at most often get the slots; the rest fold into "Sonstige".
 */
export function storeColorMap(...lists: StoreSlice[][]): Map<string, string> {
  const order: string[] = []
  for (const list of lists) {
    for (const s of list) if (!order.includes(s.store_id)) order.push(s.store_id)
  }
  return new Map(order.slice(0, SLOTS).map((id, i) => [id, `var(--series-${i + 1})`]))
}

export function toSlices(
  list: StoreSlice[],
  colors: Map<string, string>,
  value: (s: StoreSlice) => number,
): Slice[] {
  const slices: Slice[] = []
  let other = 0
  for (const s of list) {
    const color = colors.get(s.store_id)
    if (color) slices.push({ key: s.store_id, label: s.name, value: value(s), color })
    else other += value(s)
  }
  slices.sort((a, b) => b.value - a.value)
  if (other > 0) slices.push({ key: 'other', label: 'Sonstige', value: other, color: OTHER_COLOR })
  return slices
}
