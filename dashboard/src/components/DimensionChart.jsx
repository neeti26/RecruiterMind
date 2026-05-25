import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LabelList } from 'recharts'

const DIMS = [
  { key: 'technical_skill_match', label: 'Tech Skills',  color: '#6366f1' },
  { key: 'career_trajectory',     label: 'Career',       color: '#10b981' },
  { key: 'domain_depth',          label: 'Domain',       color: '#8b5cf6' },
  { key: 'seniority_alignment',   label: 'Seniority',    color: '#f59e0b' },
  { key: 'behavioral_signals',    label: 'Behavioral',   color: '#ec4899' },
  { key: 'culture_soft_fit',      label: 'Culture',      color: '#14b8a6' },
]

export default function DimensionChart({ candidates }) {
  const top = candidates.slice(0, 10)
  const data = DIMS.map(({ key, label, color }) => {
    const avg = top.reduce((s, c) => s + (c.scores?.[key] ?? 0), 0) / top.length
    return { label, avg: Math.round(avg * 100), color }
  })

  return (
    <div className="bg-[#161b27] border border-[#2a3347] rounded-2xl p-5">
      <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-4">
        Avg Scores — Top 10
      </div>
      <div className="h-[190px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 0, right: 28, top: 0, bottom: 0 }}>
            <XAxis type="number" domain={[0, 100]} hide />
            <YAxis
              type="category" dataKey="label"
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              width={68} axisLine={false} tickLine={false}
            />
            <Tooltip
              contentStyle={{ background: '#161b27', border: '1px solid #2a3347', borderRadius: 8, fontSize: 11 }}
              formatter={v => [`${v}%`, 'Avg Score']}
              cursor={{ fill: '#ffffff08' }}
            />
            <Bar dataKey="avg" radius={[0, 4, 4, 0]} maxBarSize={14}>
              {data.map((d, i) => (
                <Cell key={i} fill={d.color} fillOpacity={0.8} />
              ))}
              <LabelList
                dataKey="avg"
                position="right"
                formatter={v => `${v}%`}
                style={{ fill: '#64748b', fontSize: 10, fontFamily: 'monospace' }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
