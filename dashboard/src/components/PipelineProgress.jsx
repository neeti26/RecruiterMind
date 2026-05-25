import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, Circle, Loader2, Cpu, Database, Search, BarChart3, Trophy, MessageSquare, Brain } from 'lucide-react'
import { useEffect, useRef } from 'react'

const STAGES = [
  { id: 'jd',         label: 'JD Intelligence',       desc: 'LLM semantic decomposition',              icon: Brain },
  { id: 'profile',    label: 'Candidate Profiling',    desc: 'Structured profile extraction',           icon: Database },
  { id: 'embed',      label: 'Semantic Embeddings',    desc: 'nomic-embed-text-v1.5 · 768-dim',         icon: Cpu },
  { id: 'retrieve',   label: 'Hybrid Retrieval',       desc: 'FAISS + BM25 · Reciprocal Rank Fusion',   icon: Search },
  { id: 'score',      label: '7-Dimension Scoring',    desc: 'Skills · Trajectory · Depth · Seniority', icon: BarChart3 },
  { id: 'tournament', label: 'LLM Tournament',         desc: 'Listwise ranking · Plackett-Luce',        icon: Trophy },
  { id: 'explain',    label: 'Explainability',         desc: 'Recruiter narratives · Bias audit',       icon: MessageSquare },
]

function getStatus(stageId, logs) {
  const rel = logs.filter(l => l.stage === stageId)
  if (rel.some(l => l.status === 'done')) return 'done'
  if (rel.some(l => l.status === 'running')) return 'running'
  return 'pending'
}

function getOverallProgress(logs) {
  const done = STAGES.filter(s => getStatus(s.id, logs) === 'done').length
  return Math.round((done / STAGES.length) * 100)
}

export default function PipelineProgress({ logs }) {
  const logRef = useRef()
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [logs])

  const progress = getOverallProgress(logs)
  const currentStage = STAGES.find(s => getStatus(s.id, logs) === 'running')

  return (
    <div className="pt-8 max-w-4xl mx-auto">

      {/* Header */}
      <div className="text-center mb-8">
        <motion.div
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="inline-flex items-center gap-2 text-indigo-400 text-sm font-medium mb-3"
        >
          <Loader2 size={14} className="animate-spin" />
          {currentStage ? `Running: ${currentStage.label}` : 'Initializing pipeline...'}
        </motion.div>
        <h2 className="text-2xl font-bold text-white mb-4">Analyzing candidates</h2>

        {/* Progress bar */}
        <div className="max-w-sm mx-auto">
          <div className="flex justify-between text-xs text-slate-500 mb-1.5">
            <span>Pipeline progress</span>
            <span className="tabular-nums">{progress}%</span>
          </div>
          <div className="h-1.5 bg-[#1e2535] rounded-full overflow-hidden">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-indigo-600 to-violet-500"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
            />
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">

        {/* Stage timeline */}
        <div className="bg-[#161b27] border border-[#2a3347] rounded-2xl p-5">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-4">Pipeline Stages</div>
          <div className="relative">
            {/* Vertical line */}
            <div className="absolute left-[18px] top-4 bottom-4 w-px bg-[#2a3347]" />

            <div className="space-y-1">
              {STAGES.map((stage, i) => {
                const status = getStatus(stage.id, logs)
                const Icon = stage.icon
                return (
                  <motion.div key={stage.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.04 }}
                    className={`relative flex items-start gap-3 p-2.5 rounded-xl transition-all duration-300
                      ${status === 'running' ? 'bg-indigo-500/10' : ''}
                      ${status === 'done' ? 'opacity-70' : ''}`}
                  >
                    {/* Icon circle */}
                    <div className={`relative z-10 flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-all
                      ${status === 'done' ? 'bg-emerald-500/15 border border-emerald-500/25' :
                        status === 'running' ? 'bg-indigo-500/20 border border-indigo-500/30' :
                        'bg-[#1e2535] border border-[#2a3347]'}`}
                    >
                      {status === 'done'
                        ? <CheckCircle2 size={15} className="text-emerald-400" />
                        : status === 'running'
                        ? <Loader2 size={15} className="text-indigo-400 animate-spin" />
                        : <Icon size={14} className="text-slate-600" />}
                    </div>

                    <div className="pt-1">
                      <div className={`text-[13px] font-medium leading-tight
                        ${status === 'done' ? 'text-emerald-400' :
                          status === 'running' ? 'text-indigo-300' : 'text-slate-500'}`}>
                        {stage.label}
                      </div>
                      <div className="text-[11px] text-slate-600 mt-0.5">{stage.desc}</div>
                    </div>
                  </motion.div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Live log */}
        <div className="bg-[#161b27] border border-[#2a3347] rounded-2xl p-5 flex flex-col">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-4">Live Output</div>
          <div
            ref={logRef}
            className="flex-1 overflow-y-auto space-y-1 font-mono text-[11px] max-h-[380px] pr-1"
          >
            <AnimatePresence initial={false}>
              {logs.map((log, i) => (
                <motion.div key={i}
                  initial={{ opacity: 0, y: 3 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.15 }}
                  className={`flex gap-2 leading-relaxed
                    ${log.level === 'error' ? 'text-red-400' :
                      log.level === 'success' ? 'text-emerald-400' :
                      log.status === 'done' ? 'text-emerald-400/70' :
                      log.status === 'running' ? 'text-indigo-300' :
                      'text-slate-400'}`}
                >
                  <span className="text-slate-600 flex-shrink-0 tabular-nums">{log.time}</span>
                  <span className="break-all">{log.message}</span>
                </motion.div>
              ))}
            </AnimatePresence>
            {logs.length === 0 && (
              <div className="text-slate-600 italic">Connecting to pipeline...</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
