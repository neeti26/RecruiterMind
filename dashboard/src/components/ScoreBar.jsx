import { motion } from 'framer-motion'

export default function ScoreBar({ label, value, color, delay = 0 }) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)))
  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className="text-[11px] text-slate-500">{label}</span>
        <span className="text-[11px] font-mono font-semibold tabular-nums" style={{ color }}>
          {pct}%
        </span>
      </div>
      <div className="h-1 bg-[#1e2535] rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.7, ease: [0.25, 0.46, 0.45, 0.94], delay: 0.15 + delay }}
          className="h-full rounded-full"
          style={{ background: `linear-gradient(90deg, ${color}99, ${color})` }}
        />
      </div>
    </div>
  )
}
