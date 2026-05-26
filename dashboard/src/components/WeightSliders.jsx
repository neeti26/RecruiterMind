import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { SlidersHorizontal, RotateCcw, Zap } from 'lucide-react'

const DIMS = [
  { key: 'technical_skill_match', label: 'Tech Skills',   color: '#6366f1', default: 0.28 },
  { key: 'career_trajectory',     label: 'Career Traj.',  color: '#10b981', default: 0.18 },
  { key: 'domain_depth',          label: 'Domain Depth',  color: '#8b5cf6', default: 0.16 },
  { key: 'seniority_alignment',   label: 'Seniority Fit', color: '#f59e0b', default: 0.14 },
  { key: 'behavioral_signals',    label: 'Behavioral',    color: '#ec4899', default: 0.10 },
  { key: 'culture_soft_fit',      label: 'Culture Fit',   color: '#14b8a6', default: 0.08 },
  { key: 'risk_penalty',          label: 'Risk Penalty',  color: '#ef4444', default: 0.06 },
]

const PRESETS = {
  balanced:    { label: 'Balanced',     weights: { technical_skill_match: 0.28, career_trajectory: 0.18, domain_depth: 0.16, seniority_alignment: 0.14, behavioral_signals: 0.10, culture_soft_fit: 0.08, risk_penalty: 0.06 } },
  techHeavy:   { label: 'Tech-Heavy',   weights: { technical_skill_match: 0.45, career_trajectory: 0.15, domain_depth: 0.15, seniority_alignment: 0.10, behavioral_signals: 0.05, culture_soft_fit: 0.05, risk_penalty: 0.05 } },
  leadership:  { label: 'Leadership',   weights: { technical_skill_match: 0.20, career_trajectory: 0.30, domain_depth: 0.15, seniority_alignment: 0.20, behavioral_signals: 0.05, culture_soft_fit: 0.05, risk_penalty: 0.05 } },
  cultural:    { label: 'Culture-First', weights: { technical_skill_match: 0.20, career_trajectory: 0.15, domain_depth: 0.15, seniority_alignment: 0.10, behavioral_signals: 0.15, culture_soft_fit: 0.20, risk_penalty: 0.05 } },
}

export default function WeightSliders({ candidates, onRerank, isReranking }) {
  const [open, setOpen] = useState(false)
  const [weights, setWeights] = useState(() =>
    Object.fromEntries(DIMS.map(d => [d.key, d.default]))
  )
  const [activePreset, setActivePreset] = useState('balanced')

  const total = Object.values(weights).reduce((s, v) => s + v, 0)
  const isValid = Math.abs(total - 1.0) < 0.01

  const setWeight = useCallback((key, val) => {
    setWeights(prev => ({ ...prev, [key]: val }))
    setActivePreset(null)
  }, [])

  const applyPreset = (presetKey) => {
    setWeights({ ...PRESETS[presetKey].weights })
    setActivePreset(presetKey)
  }

  const reset = () => applyPreset('balanced')

  const handleApply = () => {
    if (!isValid) return
    onRerank(weights)
  }

  return (
    <div className="bg-[#161b27] border border-[#2a3347] rounded-2xl overflow-hidden">
      {/* Header toggle */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-[#1e2535] transition-colors"
      >
        <div className="flex items-center gap-2">
          <SlidersHorizontal size={13} className="text-indigo-400" />
          <span className="text-sm font-semibold text-white">Adjust Weights</span>
          {!isValid && (
            <span className="text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">
              {(total * 100).toFixed(0)}% ≠ 100%
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {activePreset && (
            <span className="text-[10px] text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full">
              {PRESETS[activePreset]?.label}
            </span>
          )}
          <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2 4l4 4 4-4" stroke="#64748b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </motion.div>
        </div>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-[#2a3347]"
          >
            <div className="p-4 space-y-4">
              {/* Presets */}
              <div>
                <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">Presets</div>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(PRESETS).map(([key, preset]) => (
                    <button key={key} onClick={() => applyPreset(key)}
                      className={`text-[11px] px-2.5 py-1 rounded-lg border font-medium transition-all
                        ${activePreset === key
                          ? 'bg-indigo-600/20 border-indigo-500/40 text-indigo-300'
                          : 'bg-[#1e2535] border-[#2a3347] text-slate-400 hover:text-slate-300'}`}>
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Sliders */}
              <div className="space-y-3">
                {DIMS.map(dim => (
                  <div key={dim.key}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] text-slate-400">{dim.label}</span>
                      <span className="text-[11px] font-mono tabular-nums" style={{ color: dim.color }}>
                        {Math.round(weights[dim.key] * 100)}%
                      </span>
                    </div>
                    <div className="relative h-1.5 bg-[#1e2535] rounded-full">
                      <div
                        className="absolute h-full rounded-full transition-all"
                        style={{ width: `${weights[dim.key] * 100}%`, background: dim.color }}
                      />
                      <input
                        type="range" min="0" max="0.6" step="0.01"
                        value={weights[dim.key]}
                        onChange={e => setWeight(dim.key, parseFloat(e.target.value))}
                        className="absolute inset-0 w-full opacity-0 cursor-pointer h-full"
                      />
                    </div>
                  </div>
                ))}
              </div>

              {/* Total indicator */}
              <div className={`flex items-center justify-between text-xs rounded-lg px-3 py-2 ${
                isValid ? 'bg-emerald-500/8 border border-emerald-500/15' : 'bg-amber-500/8 border border-amber-500/15'
              }`}>
                <span className={isValid ? 'text-emerald-400' : 'text-amber-400'}>
                  Total: {(total * 100).toFixed(0)}%
                </span>
                <span className={`text-[10px] ${isValid ? 'text-emerald-500' : 'text-amber-500'}`}>
                  {isValid ? '✓ Valid' : 'Must equal 100%'}
                </span>
              </div>

              {/* Actions */}
              <div className="flex gap-2">
                <button onClick={reset}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#2a3347] text-slate-400 hover:text-slate-300 text-xs transition-colors">
                  <RotateCcw size={11} /> Reset
                </button>
                <button
                  onClick={handleApply}
                  disabled={!isValid || isReranking}
                  className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold transition-all
                    ${isValid && !isReranking
                      ? 'bg-indigo-600 hover:bg-indigo-500 text-white'
                      : 'bg-[#1e2535] text-slate-600 cursor-not-allowed border border-[#2a3347]'}`}>
                  {isReranking
                    ? <><span className="w-3 h-3 border border-white/30 border-t-white rounded-full animate-spin" /> Reranking...</>
                    : <><Zap size={11} /> Apply & Rerank</>}
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
