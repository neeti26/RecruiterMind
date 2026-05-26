import { AlertTriangle, Clock, CheckCircle2 } from 'lucide-react'

/**
 * Shows timeline discrepancy flags on a candidate card.
 * High severity = red, medium = amber, low = yellow.
 */
export default function DiscrepancyBadge({ validation }) {
  if (!validation || !validation.has_discrepancy) return null

  const flags = validation.flags || []
  const highFlags = flags.filter(f => f.severity === 'high')
  const medFlags  = flags.filter(f => f.severity === 'medium')

  const severity = highFlags.length > 0 ? 'high' : medFlags.length > 0 ? 'medium' : 'low'
  const cls = {
    high:   'bg-red-500/10 border-red-500/20 text-red-400',
    medium: 'bg-amber-500/10 border-amber-500/20 text-amber-400',
    low:    'bg-yellow-500/10 border-yellow-500/20 text-yellow-400',
  }[severity]

  return (
    <div className={`rounded-xl border p-3 ${cls} space-y-1.5`}>
      <div className="flex items-center gap-1.5 text-[11px] font-semibold">
        <AlertTriangle size={11} />
        Timeline Discrepancy Detected
        <span className="ml-auto opacity-60 font-normal">
          Trust: {Math.round((validation.trust_score ?? 1) * 100)}%
        </span>
      </div>
      {flags.slice(0, 3).map((f, i) => (
        <div key={i} className="flex gap-1.5 text-[10px] opacity-80">
          <Clock size={9} className="flex-shrink-0 mt-0.5" />
          <span>{f.description}</span>
        </div>
      ))}
      {validation.claimed_years > 0 && validation.timeline_years > 0 && (
        <div className="text-[10px] opacity-60 font-mono">
          Claimed: {validation.claimed_years}y · Timeline: {validation.timeline_years}y
        </div>
      )}
    </div>
  )
}
