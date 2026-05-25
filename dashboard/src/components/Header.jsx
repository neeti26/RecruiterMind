import { motion } from 'framer-motion'
import { Brain, RotateCcw, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'
import { useEffect, useState } from 'react'

const STATUS = {
  idle:    { icon: null,         text: null,               cls: '' },
  running: { icon: Loader2,      text: 'Running pipeline', cls: 'text-amber-400', spin: true },
  done:    { icon: CheckCircle2, text: 'Analysis complete',cls: 'text-emerald-400' },
  error:   { icon: AlertCircle,  text: 'Error',            cls: 'text-red-400' },
}

export default function Header({ phase, onReset }) {
  const [backendOk, setBackendOk] = useState(null) // null=checking, true, false

  useEffect(() => {
    fetch((import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000') + '/api/health')
      .then(r => r.json())
      .then(d => setBackendOk(d.status === 'ok'))
      .catch(() => setBackendOk(false))
  }, [])

  const s = STATUS[phase] || STATUS.idle
  const Icon = s.icon

  return (
    <header className="sticky top-0 z-50 border-b border-[#2a3347] bg-[#0f1117]/90 backdrop-blur-md">
      <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center justify-between gap-4">

        {/* Logo */}
        <div className="flex items-center gap-2.5 flex-shrink-0">
          <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center">
            <Brain size={15} className="text-indigo-400" />
          </div>
          <span className="font-bold text-white text-[15px] tracking-tight">RecruiterMind</span>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3">

          {/* Pipeline status */}
          {Icon && (
            <motion.div initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }}
              className={`flex items-center gap-1.5 text-xs font-medium ${s.cls}`}>
              <Icon size={13} className={s.spin ? 'animate-spin' : ''} />
              {s.text}
            </motion.div>
          )}

          {/* Backend health */}
          {backendOk === false && (
            <div className="flex items-center gap-1.5 text-xs text-red-400 bg-red-500/10 border border-red-500/20 px-2.5 py-1 rounded-lg">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
              Backend offline
            </div>
          )}

          {/* Reset */}
          {onReset && (
            <button onClick={onReset}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#2a3347] text-slate-400 hover:text-white hover:border-[#3a4357] transition-all text-xs">
              <RotateCcw size={12} />
              New analysis
            </button>
          )}

          <div className="hidden sm:flex items-center gap-1.5 text-[11px] text-slate-600 bg-[#161b27] border border-[#2a3347] px-2.5 py-1 rounded-lg">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500/60" />
            Hack2Skill India Runs 2026
          </div>
        </div>
      </div>
    </header>
  )
}
