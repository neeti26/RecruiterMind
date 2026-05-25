import { motion } from 'framer-motion'
import { Shield, ShieldAlert, ShieldCheck } from 'lucide-react'

export default function BiasAudit({ audit }) {
  if (!audit) return null

  const passed = audit.audit_passed
  const flags = audit.bias_flags || []

  return (
    <div className="bg-[#161b27] border border-[#2a3347] rounded-2xl p-5">
      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">Bias Audit</div>

      <div className={`flex items-center gap-3 p-3 rounded-xl mb-3 ${passed ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-amber-500/10 border border-amber-500/20'}`}>
        {passed
          ? <ShieldCheck size={18} className="text-emerald-400 flex-shrink-0" />
          : <ShieldAlert size={18} className="text-amber-400 flex-shrink-0" />}
        <div>
          <div className={`text-sm font-semibold ${passed ? 'text-emerald-400' : 'text-amber-400'}`}>
            {passed ? 'Audit Passed' : 'Review Recommended'}
          </div>
          <div className="text-xs text-slate-500 mt-0.5">
            {passed ? 'No significant bias detected' : `${flags.length} flag(s) found`}
          </div>
        </div>
      </div>

      {flags.length > 0 && (
        <div className="space-y-2">
          {flags.map((f, i) => (
            <div key={i} className="text-xs text-amber-300/80 bg-amber-500/5 rounded-lg p-2 border border-amber-500/10">
              {f}
            </div>
          ))}
        </div>
      )}

      <div className="mt-3 text-xs text-slate-600 leading-relaxed">
        Candidates evaluated purely on skills, experience, and trajectory. Name and demographic signals are neutralized.
      </div>
    </div>
  )
}
