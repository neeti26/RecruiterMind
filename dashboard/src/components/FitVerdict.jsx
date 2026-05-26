import { CheckCircle2, AlertCircle, Users } from 'lucide-react'

/**
 * Renders the 3-bullet AI fit verdict:
 * ✅ Pros  ⚠ Gaps  👥 Culture/Behavioral
 */
export default function FitVerdict({ candidate }) {
  const { key_strength, key_concern, why_hire, explanation, hire_recommendation } = candidate

  if (!why_hire && !explanation) return null

  // Parse explanation into structured bullets if possible
  const pros = key_strength || ''
  const gap = key_concern && key_concern !== 'None identified' ? key_concern : null
  const culture = explanation || ''

  const recColors = {
    strong_yes: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    yes:        'text-teal-400 bg-teal-500/10 border-teal-500/20',
    maybe:      'text-amber-400 bg-amber-500/10 border-amber-500/20',
    no:         'text-red-400 bg-red-500/10 border-red-500/20',
  }
  const recLabels = { strong_yes: 'Strong Yes', yes: 'Yes', maybe: 'Maybe', no: 'No' }
  const recCls = recColors[hire_recommendation] || recColors.maybe

  return (
    <div className="space-y-2">
      {/* Recommendation badge */}
      {hire_recommendation && (
        <div className={`inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-lg border ${recCls}`}>
          Hire: {recLabels[hire_recommendation] || 'Maybe'}
          {candidate.confidence > 0 && (
            <span className="opacity-50 font-normal">· {Math.round(candidate.confidence * 100)}% conf.</span>
          )}
        </div>
      )}

      {/* Why hire */}
      {why_hire && (
        <div className="bg-indigo-500/8 rounded-xl p-3 border border-indigo-500/15">
          <p className="text-[12px] text-slate-200 leading-relaxed font-medium">{why_hire}</p>
        </div>
      )}

      {/* 3-bullet verdict */}
      <div className="space-y-1.5">
        {pros && (
          <div className="flex gap-2 text-[11px]">
            <CheckCircle2 size={12} className="text-emerald-400 flex-shrink-0 mt-0.5" />
            <span className="text-slate-300 leading-snug"><span className="text-emerald-400 font-medium">Strength: </span>{pros}</span>
          </div>
        )}
        {gap && (
          <div className="flex gap-2 text-[11px]">
            <AlertCircle size={12} className="text-amber-400 flex-shrink-0 mt-0.5" />
            <span className="text-slate-300 leading-snug"><span className="text-amber-400 font-medium">Gap: </span>{gap}</span>
          </div>
        )}
        {culture && (
          <div className="flex gap-2 text-[11px]">
            <Users size={12} className="text-indigo-400 flex-shrink-0 mt-0.5" />
            <span className="text-slate-400 leading-snug">{culture}</span>
          </div>
        )}
      </div>
    </div>
  )
}
