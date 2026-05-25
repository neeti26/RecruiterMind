import { useState, useRef } from 'react'
import { motion } from 'framer-motion'
import { Upload, FileText, Play, Sparkles, AlertCircle, ChevronRight } from 'lucide-react'

const SAMPLE_JD = `Senior Machine Learning Engineer — AI Platform Team

We're looking for a Senior ML Engineer to join our AI Platform team. You'll build infrastructure and models powering recommendation and personalization systems at scale.

Required:
- 5+ years of ML engineering or data science experience
- Strong Python skills — production-grade code
- PyTorch or TensorFlow for model training
- MLOps: model serving, monitoring, CI/CD for ML
- Distributed computing (Spark, Ray, or Dask)
- SQL and data warehousing
- Cloud deployment (AWS, GCP, or Azure)

Nice to Have:
- LLMs, RAG systems, vector databases
- Open-source ML contributions
- Kubernetes and Docker for ML workloads
- Recommendation systems or ranking algorithms

Culture:
- Fast-moving, high-ownership environment
- Strong engineering culture — code reviews, testing matter
- Remote-friendly, async-first communication`

const PIPELINE_STEPS = [
  'JD Intelligence — LLM extracts implicit needs, culture signals, deal-breakers',
  'Semantic Embeddings — nomic-embed-text-v1.5, 768-dim vectors per candidate',
  'Hybrid Retrieval — FAISS dense + BM25 sparse, fused via Reciprocal Rank Fusion',
  '7-Dimension Scoring — Skills · Trajectory · Domain · Seniority · Behavioral · Culture · Risk',
  'LLM Tournament — Listwise mini-tournaments with Plackett-Luce aggregation',
]

export default function InputPanel({ onSubmit }) {
  const [jdText, setJdText] = useState('')
  const [csvContent, setCsvContent] = useState('')
  const [csvName, setCsvName] = useState('')
  const [csvRows, setCsvRows] = useState(0)
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef()

  const handleFile = (file) => {
    if (!file) return
    const reader = new FileReader()
    reader.onload = (e) => {
      const text = e.target.result
      setCsvContent(text)
      setCsvName(file.name)
      setCsvRows(text.split('\n').filter(Boolean).length - 1)
    }
    reader.readAsText(file)
  }

  const useSample = () => {
    setJdText(SAMPLE_JD)
    fetch((import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000') + '/api/sample-csv')
      .then(r => r.text())
      .then(text => {
        setCsvContent(text)
        setCsvName('sample_candidates.csv')
        setCsvRows(text.split('\n').filter(Boolean).length - 1)
      })
      .catch(() => { setCsvName('sample_candidates.csv'); setCsvRows(20) })
  }

  const canSubmit = jdText.trim().length > 50

  return (
    <div className="pt-10 max-w-5xl mx-auto">

      {/* Hero */}
      <div className="mb-8">
        <motion.h1 initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          className="text-3xl font-bold text-white tracking-tight mb-2">
          Rank candidates like a{' '}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-violet-400">
            great recruiter
          </span>
        </motion.h1>
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}
          className="text-slate-400 text-sm">
          Paste a job description, upload your candidates CSV, and get a ranked shortlist with explanations.
        </motion.p>
      </div>

      <div className="grid lg:grid-cols-5 gap-5">

        {/* Left: inputs (3 cols) */}
        <div className="lg:col-span-3 space-y-4">

          {/* JD */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
            className="bg-[#161b27] border border-[#2a3347] rounded-2xl p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <FileText size={14} className="text-indigo-400" />
                <span className="text-sm font-semibold text-white">Job Description</span>
              </div>
              <button onClick={useSample}
                className="flex items-center gap-1 text-[11px] text-indigo-400 hover:text-indigo-300 transition-colors">
                <Sparkles size={10} />
                Load sample
              </button>
            </div>
            <textarea
              value={jdText}
              onChange={e => setJdText(e.target.value)}
              placeholder="Paste the full job description — role, requirements, responsibilities, culture signals..."
              className="w-full h-52 bg-[#0f1117] border border-[#2a3347] rounded-xl p-3.5 text-[13px] text-slate-300 placeholder-slate-600 resize-none focus:outline-none focus:border-indigo-500/50 transition-colors font-mono leading-relaxed"
            />
            {jdText.length > 0 && jdText.length < 50 && (
              <div className="flex items-center gap-1.5 mt-2 text-xs text-amber-400">
                <AlertCircle size={11} /> Add more detail for better results
              </div>
            )}
          </motion.div>

          {/* CSV */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
            className="bg-[#161b27] border border-[#2a3347] rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-3">
              <Upload size={14} className="text-violet-400" />
              <span className="text-sm font-semibold text-white">Candidates CSV</span>
              <span className="ml-auto text-[11px] text-slate-500">optional — uses built-in sample if empty</span>
            </div>

            <div
              onDragOver={e => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={e => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]) }}
              onClick={() => fileRef.current?.click()}
              className={`h-24 border-2 border-dashed rounded-xl flex items-center justify-center gap-3 cursor-pointer transition-all
                ${dragOver ? 'border-indigo-500 bg-indigo-500/5' : 'border-[#2a3347] hover:border-indigo-500/30 hover:bg-[#1a2030]'}`}
            >
              <input ref={fileRef} type="file" accept=".csv" className="hidden"
                onChange={e => handleFile(e.target.files[0])} />

              {csvName ? (
                <>
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center flex-shrink-0">
                    <FileText size={14} className="text-emerald-400" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-white">{csvName}</div>
                    <div className="text-xs text-emerald-400">{csvRows} candidates · click to replace</div>
                  </div>
                </>
              ) : (
                <>
                  <Upload size={18} className={dragOver ? 'text-indigo-400' : 'text-slate-600'} />
                  <div className="text-sm text-slate-500">
                    {dragOver ? 'Drop it!' : 'Drop CSV or click to browse'}
                  </div>
                </>
              )}
            </div>

            {/* Column hint */}
            <div className="mt-2.5 text-[11px] text-slate-600 flex flex-wrap gap-x-3 gap-y-0.5">
              <span className="text-slate-500 font-medium">Expected columns:</span>
              {['name', 'current_title', 'years_experience', 'skills', 'location', 'github_repos'].map(c => (
                <span key={c} className="font-mono">{c}</span>
              ))}
            </div>
          </motion.div>

          {/* Submit */}
          <motion.button
            onClick={() => onSubmit({ jdText, candidatesCSV: csvContent })}
            disabled={!canSubmit}
            whileHover={canSubmit ? { scale: 1.01 } : {}}
            whileTap={canSubmit ? { scale: 0.99 } : {}}
            className={`w-full flex items-center justify-center gap-2.5 py-3.5 rounded-xl font-semibold text-sm transition-all
              ${canSubmit
                ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20'
                : 'bg-[#1e2535] text-slate-600 cursor-not-allowed border border-[#2a3347]'}`}
          >
            <Play size={14} />
            Run AI Pipeline
            {canSubmit && <span className="text-indigo-300 font-normal text-xs">· {csvRows || 20} candidates</span>}
          </motion.button>
        </div>

        {/* Right: pipeline explainer (2 cols) */}
        <motion.div initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}
          className="lg:col-span-2 bg-[#161b27] border border-[#2a3347] rounded-2xl p-5">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-4">How it works</div>
          <div className="space-y-3">
            {PIPELINE_STEPS.map((step, i) => {
              const [title, desc] = step.split(' — ')
              return (
                <div key={i} className="flex gap-3">
                  <div className="flex-shrink-0 w-5 h-5 rounded-md bg-indigo-600/15 border border-indigo-500/20 flex items-center justify-center mt-0.5">
                    <span className="text-[9px] font-bold text-indigo-400">{i + 1}</span>
                  </div>
                  <div>
                    <div className="text-[12px] font-semibold text-white leading-tight">{title}</div>
                    <div className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">{desc}</div>
                  </div>
                </div>
              )
            })}
          </div>

          <div className="mt-5 pt-4 border-t border-[#2a3347]">
            <div className="text-[11px] text-slate-600 leading-relaxed">
              No LLM key needed for core ranking. Add{' '}
              <code className="text-indigo-400 bg-indigo-500/10 px-1 rounded">GROQ_API_KEY</code>{' '}
              to <code className="text-slate-400">.env</code> to unlock tournament reranking.
            </div>
          </div>
        </motion.div>

      </div>
    </div>
  )
}
