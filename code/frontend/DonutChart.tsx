import { useState } from 'react'

export type Slice = {
  key: string
  label: string
  value: number
  /** CSS color of the slice (a categorical slot, or the "other" gray) */
  color: string
}

const SIZE = 160
const RADIUS = 72
const THICKNESS = 26

function arcPath(start: number, end: number): string {
  const r0 = RADIUS - THICKNESS
  const point = (r: number, angle: number) => [
    SIZE / 2 + r * Math.sin(angle),
    SIZE / 2 - r * Math.cos(angle),
  ]
  const large = end - start > Math.PI ? 1 : 0
  const [x1, y1] = point(RADIUS, start)
  const [x2, y2] = point(RADIUS, end)
  const [x3, y3] = point(r0, end)
  const [x4, y4] = point(r0, start)
  return [
    `M ${x1} ${y1}`,
    `A ${RADIUS} ${RADIUS} 0 ${large} 1 ${x2} ${y2}`,
    `L ${x3} ${y3}`,
    `A ${r0} ${r0} 0 ${large} 0 ${x4} ${y4}`,
    'Z',
  ].join(' ')
}

/**
 * Donut with a legend that doubles as the table view: every slice is listed
 * with its value and share, so identity never depends on color alone.
 */
export function DonutChart({
  title,
  slices,
  format,
  center,
  centerCaption,
}: {
  title: string
  slices: Slice[]
  format: (value: number) => string
  center: string
  centerCaption: string
}) {
  const [active, setActive] = useState<string | null>(null)
  const total = slices.reduce((sum, s) => sum + s.value, 0)
  const share = (value: number) => `${Math.round((value / total) * 100)} %`

  // Cumulative start/end angle of every slice
  const arcs = slices.map((s, i) => {
    const before = slices.slice(0, i).reduce((sum, p) => sum + p.value, 0)
    const start = (before / total) * 2 * Math.PI
    return { ...s, start, end: start + (s.value / total) * 2 * Math.PI }
  })
  const activeSlice = slices.find((s) => s.key === active)

  return (
    <figure className="donut">
      <div className="donut-plot">
        <svg
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          role="img"
          aria-label={`${title}: ${slices.map((s) => `${s.label} ${format(s.value)}`).join(', ')}`}
        >
          {arcs.length === 1 ? (
            <circle
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={RADIUS - THICKNESS / 2}
              fill="none"
              stroke={arcs[0].color}
              strokeWidth={THICKNESS}
            />
          ) : (
            arcs.map((a) => (
              <path
                key={a.key}
                d={arcPath(a.start, a.end)}
                fill={a.color}
                className={`donut-slice${active && active !== a.key ? ' dimmed' : ''}`}
                onMouseEnter={() => setActive(a.key)}
                onMouseLeave={() => setActive(null)}
              />
            ))
          )}
        </svg>
        <div className="donut-center" aria-hidden="true">
          {activeSlice ? (
            <>
              <strong>{format(activeSlice.value)}</strong>
              <span>
                {activeSlice.label} · {share(activeSlice.value)}
              </span>
            </>
          ) : (
            <>
              <strong>{center}</strong>
              <span>{centerCaption}</span>
            </>
          )}
        </div>
      </div>

      <ul className="donut-legend" aria-label={title}>
        {slices.map((s) => (
          <li
            key={s.key}
            className={active === s.key ? 'active' : undefined}
            onMouseEnter={() => setActive(s.key)}
            onMouseLeave={() => setActive(null)}
          >
            <span className="swatch" style={{ background: s.color }} aria-hidden="true" />
            <span className="legend-name">{s.label}</span>
            <span className="legend-value">{format(s.value)}</span>
            <span className="legend-share">{share(s.value)}</span>
          </li>
        ))}
      </ul>
    </figure>
  )
}
