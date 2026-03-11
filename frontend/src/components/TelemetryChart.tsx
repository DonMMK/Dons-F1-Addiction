import {
  ResponsiveContainer,
  LineChart,
  AreaChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from 'recharts'

interface Props {
  title: string
  data: Record<string, number>[]
  dataKey1: string
  dataKey2?: string
  color1?: string
  color2?: string
  isArea?: boolean
}

export default function TelemetryChart({
  title,
  data,
  dataKey1,
  dataKey2,
  color1 = 'var(--f1-red)',
  color2 = 'var(--team-mercedes)',
  isArea = false,
}: Props) {
  const Chart = isArea ? AreaChart : LineChart

  return (
    <div className="chart-card">
      <div className="chart-card__title">{title}</div>
      <ResponsiveContainer width="100%" height={220}>
        <Chart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2d2d3f" />
          <XAxis
            dataKey="distance"
            tick={{ fill: '#949aab', fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: '#2d2d3f' }}
          />
          <YAxis
            tick={{ fill: '#949aab', fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: '#2d2d3f' }}
          />
          <Tooltip
            contentStyle={{
              background: '#1e1e2e',
              border: '1px solid #38384d',
              borderRadius: 4,
              fontSize: 12,
            }}
          />

          {isArea ? (
            <>
              <ReferenceLine y={0} stroke="#555" />
              <Area
                type="monotone"
                dataKey={dataKey1}
                stroke={color1}
                fill={color1}
                fillOpacity={0.2}
                dot={false}
                isAnimationActive={false}
              />
            </>
          ) : (
            <>
              <Line
                type="monotone"
                dataKey={dataKey1}
                stroke={color1}
                dot={false}
                strokeWidth={2}
                isAnimationActive={false}
              />
              {dataKey2 && (
                <Line
                  type="monotone"
                  dataKey={dataKey2}
                  stroke={color2}
                  dot={false}
                  strokeWidth={2}
                  isAnimationActive={false}
                />
              )}
            </>
          )}
        </Chart>
      </ResponsiveContainer>
    </div>
  )
}
