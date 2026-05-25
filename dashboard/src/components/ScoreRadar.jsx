import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Radar, ResponsiveContainer, Tooltip
} from 'recharts'

export default function ScoreRadar({ dims }) {
  const data = dims.map(d => ({
    subject: d.short || d.label,
    value: Math.round(d.value * 100),
    fullMark: 100,
  }))

  return (
    <div className="h-[190px]">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 16 }}>
          <PolarGrid stroke="#2a3347" gridType="polygon" />
          <PolarAngleAxis
            dataKey="subject"
            tick={{ fill: '#64748b', fontSize: 10, fontWeight: 500 }}
          />
          <PolarRadiusAxis
            angle={90} domain={[0, 100]}
            tick={{ fill: '#334155', fontSize: 8 }}
            tickCount={4}
            axisLine={false}
          />
          <Radar
            name="Score"
            dataKey="value"
            stroke="#6366f1"
            fill="#6366f1"
            fillOpacity={0.18}
            strokeWidth={1.5}
            dot={{ fill: '#6366f1', r: 2.5, strokeWidth: 0 }}
          />
          <Tooltip
            contentStyle={{
              background: '#161b27',
              border: '1px solid #2a3347',
              borderRadius: 8,
              fontSize: 11,
              padding: '6px 10px',
            }}
            labelStyle={{ color: '#e2e8f0', fontWeight: 600 }}
            formatter={v => [`${v}%`, 'Score']}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
