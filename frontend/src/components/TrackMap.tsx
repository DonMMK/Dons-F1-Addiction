import { useMemo } from 'react'

interface Props {
  x1: number[]
  y1: number[]
  x2?: number[]
  y2?: number[]
  label1: string
  label2?: string
}

/**
 * Render an SVG track map with one or two driver paths.
 * Coordinates are normalised to fit a 1000×600 viewBox.
 */
export default function TrackMap({ x1, y1, x2, y2, label1, label2 }: Props) {
  const { path1, path2 } = useMemo(() => {
    // Combine all points for shared bounds
    const allX = x2 ? [...x1, ...x2] : x1
    const allY = y2 ? [...y1, ...y2] : y1
    const minX = Math.min(...allX)
    const maxX = Math.max(...allX)
    const minY = Math.min(...allY)
    const maxY = Math.max(...allY)
    const rangeX = maxX - minX || 1
    const rangeY = maxY - minY || 1

    const PAD = 40
    const W = 1000 - PAD * 2
    const H = 600 - PAD * 2

    const scale = Math.min(W / rangeX, H / rangeY)
    const offsetX = PAD + (W - rangeX * scale) / 2
    const offsetY = PAD + (H - rangeY * scale) / 2

    const norm = (xs: number[], ys: number[]) => {
      // Sample every 3rd point for performance
      const step = Math.max(1, Math.floor(xs.length / 400))
      const pts: string[] = []
      for (let i = 0; i < xs.length; i += step) {
        const nx = offsetX + (xs[i] - minX) * scale
        const ny = offsetY + (ys[i] - minY) * scale
        pts.push(`${nx.toFixed(1)},${ny.toFixed(1)}`)
      }
      return pts.join(' ')
    }

    return {
      path1: norm(x1, y1),
      path2: x2 && y2 ? norm(x2, y2) : undefined,
    }
  }, [x1, y1, x2, y2])

  return (
    <div className="track-map">
      <svg viewBox="0 0 1000 600" preserveAspectRatio="xMidYMid meet">
        {/* Track outline (driver 1 path acts as reference) */}
        <polyline
          points={path1}
          fill="none"
          stroke="#333"
          strokeWidth="10"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Driver 2 path */}
        {path2 && (
          <polyline
            points={path2}
            fill="none"
            stroke="var(--team-mercedes)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity={0.8}
          />
        )}

        {/* Driver 1 path */}
        <polyline
          points={path1}
          fill="none"
          stroke="var(--f1-red)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={0.9}
        />

        {/* Legend */}
        <rect x="20" y="560" width="12" height="12" rx="2" fill="var(--f1-red)" />
        <text x="38" y="571" fill="var(--f1-white)" fontSize="12" fontFamily="Titillium Web, sans-serif">{label1}</text>

        {label2 && (
          <>
            <rect x="100" y="560" width="12" height="12" rx="2" fill="var(--team-mercedes)" />
            <text x="118" y="571" fill="var(--f1-white)" fontSize="12" fontFamily="Titillium Web, sans-serif">{label2}</text>
          </>
        )}
      </svg>
    </div>
  )
}
