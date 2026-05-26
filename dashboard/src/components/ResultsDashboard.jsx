import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Users, TrendingUp, Award, Download, ChevronDown, ChevronUp,
  Shield, SortAsc, Star, Filter, X, Briefcase, AlertTriangle,
  Eye, EyeOff, Cpu, CheckCircle2
} from 'lucide-react'
import ScoreBar from './ScoreBar'
import ScoreRadar from './ScoreRadar'
import DimensionChart from './DimensionChart'
import BiasAudit from './BiasAudit'
import AnimatedNumber from './AnimatedNumber'
import WeightSliders from './WeightSliders'
import FitVerdict from './FitVerdict'
import DiscrepancyBadge from './DiscrepancyBadge'

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

const RANK_STYLES = {
  1: { ring: 'ring-1 ring-amber-500/40', bg: 'from-amber-500/6', badge: 'bg-amber-500/15 text-amber-300 border-amber-500/25', label: '🥇 Top Pick' },
  2: { ring: 'ring-1 ring-slate-400/25', bg: 'from-slate-400/4', badge: 'bg-slate-500/15 text-slate-300 border-slate-400/25', label: '🥈 Runner Up' },
  3: { ring: 'ring-1 ring-orange-500/25', bg: 'from-orange-500/5', badge: 'bg-orange-500/15 text-orange-300 border-orange-500/25', label: '🥉 Strong Fit' },
}

const DIM_META = [
  { key: 'technical_skill_match', label: 'Tech Skills',   short: 'Skills',  color: '#6366f1' },
  { key: 'career_trajectory',     label: 'Career Traj.',  short: 'Career',  color: '#10b981' },
  { key: 'domain_depth',          label: 'Domain Depth',  short: 'Domain',  color: '#8b5cf6' },
  { key: 'seniority_alignment',   label: 'Seniority Fit', short: 'Level',   color: '#f59e0b' },
  { key: 'behavioral_signals',    label: 'Behavioral',    short: 'Signals', color: '#ec4899' },
  { key: 'culture_soft_fit',      label: 'Culture Fit',   short: 'Culture', color: '#14b8a6' },
]

const SORT_OPTIONS = [
  { value: 'rank',      label: 'Best Match' },
  { value: 'skills',    label: 'Tech Skills' },
  { value: 'career',    label: 'Career Traj.' },
  { value: 'seniority', label: 'Seniority Fit' },
  { value: 'exp',       label: 'Experience' },
  { value: 'trust',     label: 'Trust Score' },
]

function downloadCSV(candidates, filename = 'ranked_candidates.csv') {
  const rows = candidates.map(c => ({
    rank: c.final_rank,
    candidate_id: c.candidate_id,
    name: c.name,
    current_title: c.current_title,
    years_experience: c.total_years_experience,
    final_score_pct: (c.final_score * 100).toFixed(2),
    hire_recommendation: c.hire_recommendation || '',
    confidence_pct: ((c.confidence ?? 0) * 100).toFixed(1),
    trust_score_pct: ((c.trust_score ?? 1) * 100).toFixed(1),
    has_discrepancy: c.has_discrepancy ? 'YES' : 'NO',
    tech_skills_pct: ((c.scores?.technical_skill_match ?? 0) * 100).toFixed(2),
    career_traj_pct: ((c.scores?.career_trajectory ?? 0) * 100).toFixed(2),
    domain_depth_pct: ((c.scores?.domain_depth ?? 0) * 100).toFixed(2),
    seniority_fit_pct: ((c.scores?.seniority_alignment ?? 0) * 100).toFixed(2),
    behavioral_pct: ((c.scores?.behavioral_signals ?? 0) * 100).toFixed(2),
    culture_fit_pct: ((c.scores?.culture_soft_fit ?? 0) * 100).toFixed(2),
    risk_penalty_pct: ((c.scores?.risk_penalty ?? 0) * 100).toFixed(2),
    cross_encoder_pct: ((c.scores?.cross_encoder_score ?? 0) * 100).toFixed(2),
    matched_skills: Array.isArray(c.matched_skills) ? c.matched_skills.join('; ') : (c.top_skills || ''),
    missing_skills: Array.isArray(c.missing_skills) ? c.missing_skills.join('; ') : '',
    critical_gaps: Array.isArray(c.critical_gaps) ? c.critical_gaps.join('; ') : '',
    primary_fit_reason: c.why_hire || c.explanation || '',
    key_strength: c.key_strength || '',
    key_concern: c.key_concern || '',
    location: c.location || '',
  }))
  const headers = Object.keys(rows[0]).join(',')
  const lines = rows.map(r =>
    Object.values(r).map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')
  )
  const blob = new Blob([[headers, ...lines].join('\n')], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
}

function ScoreRing({ score, size = 52, stroke = 4 }) {
  const r = (size - stroke * 2) / 2
  const circ = 2 * Math.PI * r
  const pct = Math.round(score * 100)
  const color = pct >= 65 ? '#10b981' : pct >= 45 ? '#6366f1' : pct >= 30 ? '#f59e0b' : '#ef4444'
  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#1e2535" strokeWidth={stroke} />
        <motion.circle cx={size/2} cy={size/2} r={r} fill="none"
          stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ - (pct / 100) * circ }}
          transition={{ duration: 0.8, ease: 'easeOut', delay: 0.1 }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <AnimatedNumber value={pct} className="text-[13px] font-bold text-white tabular-nums leading-none" />
        <span className="text-[8px] text-slate-500 leading-none">%</span>
      </div>
    </div>
  )
}

function CandidateCard({ candidate, index, shortlisted, onToggleShortlist }) {
  const [expanded, setExpanded] = useState(index < 2)
  const rank = candidate.final_rank
  const style = RANK_STYLES[rank] || { ring: '', bg: 'from-transparent', badge: 'bg-[#1e2535] text-slate-400 border-[#2a3347]', label: null }
  const dims = DIM_META.map(d => ({ ...d, value: candidate.scores?.[d.key] ?? 0 }))
  const hasRisk = (candidate.scores?.risk_penalty ?? 0) > 0.25
  const hasDiscrepancy = candidate.has_discrepancy

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.035, 0.35), duration: 0.28 }}
      className={`rounded-2xl border border-[#2a3347] ${style.ring} bg-gradient-to-br ${style.bg} to-transparent overflow-hidden`}
    >
      {/* ── Header ── */}
      <div className="p-4 flex items-center gap-3">
        <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold border ${style.badge}`}>
          {rank}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-white text-sm">{candidate.name}</span>
            {style.label && <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium border ${style.badge}`}>{style.label}</span>}
            {hasRisk && <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400"><AlertTriangle size={9} />risk</span>}
            {hasDiscrepancy && <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-400"><AlertTriangle size={9} />discrepancy</span>}
          </div>
          <div className="text-xs text-slate-400 mt-0.5 truncate">
            {[candidate.current_title, candidate.total_years_experience > 0 && `${candidate.total_years_experience}y`, candidate.location].filter(Boolean).join(' · ')}
          </div>
        </div>
        <ScoreRing score={candidate.final_score} />
        <button onClick={() => onToggleShortlist(candidate.candidate_id)}
          className={`flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center transition-all border
            ${shortlisted ? 'bg-amber-500/15 text-amber-400 border-amber-500/25' : 'bg-[#1e2535] text-slate-600 hover:text-slate-400 border-[#2a3347]'}`}>
          <Star size={12} className={shortlisted ? 'fill-current' : ''} />
        </button>
        <button onClick={() => setExpanded(e => !e)}
          className="flex-shrink-0 w-7 h-7 rounded-lg bg-[#1e2535] hover:bg-[#2a3347] flex items-center justify-center transition-colors text-slate-500 hover:text-slate-300 border border-[#2a3347]">
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      {/* ── Score bars ── */}
      <div className="px-4 pb-3 grid grid-cols-3 gap-x-5 gap-y-2">
        {dims.map(d => <ScoreBar key={d.key} label={d.short} value={d.value} color={d.color} />)}
      </div>

      {/* ── Skills ── */}
      <div className="px-4 pb-3 flex flex-wrap gap-1">
        {(Array.isArray(candidate.matched_skills) ? candidate.matched_skills : (candidate.top_skills || '').split(','))
          .slice(0, 8).map(s => s.trim()).filter(Boolean).map(s => (
          <span key={s} className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/15 text-indigo-300">{s}</span>
        ))}
        {(candidate.missing_skills || []).slice(0, 3).map(s => (
          <span key={s} className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/8 border border-red-500/15 text-red-400/80">−{s}</span>
        ))}
      </div>

      {/* ── Expanded detail ── */}
      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-[#2a3347]/50">
            <div className="p-4 grid md:grid-cols-2 gap-5">
              {/* Left: radar + score table */}
              <div>
                <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">Dimension Breakdown</div>
                <ScoreRadar dims={dims} />
                <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1">
                  {[...dims, { key: 'risk_penalty', label: 'Risk Penalty', short: 'Risk', color: '#ef4444', value: candidate.scores?.risk_penalty ?? 0 },
                             { key: 'cross_encoder_score', label: 'Cross-Encoder', short: 'CE', color: '#a78bfa', value: candidate.scores?.cross_encoder_score ?? 0 }
                  ].map(d => (
                    <div key={d.key} className="flex items-center justify-between text-[11px]">
                      <span className="text-slate-500">{d.label}</span>
                      <span className="font-mono font-semibold tabular-nums" style={{ color: d.color }}>
                        {d.key === 'risk_penalty' ? `−${Math.round(d.value * 100)}%` : `${Math.round(d.value * 100)}%`}
                      </span>
                    </div>
                  ))}
                </div>
                {/* Timeline discrepancy */}
                {hasDiscrepancy && (
                  <div className="mt-3">
                    <DiscrepancyBadge validation={candidate.timeline_validation} />
                  </div>
                )}
              </div>

              {/* Right: fit verdict + work history */}
              <div className="space-y-3">
                <FitVerdict candidate={candidate} />
                {Array.isArray(candidate.work_history) && candidate.work_history.length > 0 && (
                  <div>
                    <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <Briefcase size={10} /> Work History
                    </div>
                    <div className="space-y-1.5">
                      {candidate.work_history.slice(0, 3).map((job, i) => (
                        <div key={i} className="flex gap-2 text-[11px]">
                          <div className="w-1 h-1 rounded-full bg-slate-600 mt-1.5 flex-shrink-0" />
                          <div>
                            <span className="text-slate-300 font-medium">{job.title}</span>
                            {job.company && <span className="text-slate-500"> @ {job.company}</span>}
                            {(job.start_date || job.end_date) && (
                              <span className="text-slate-600"> · {job.start_date}–{job.end_date || 'present'}</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export default function ResultsDashboard({ results, onReset }) {
  const { candidates: initialCandidates, jd_analysis, bias_audit, meta } = results
  const [candidates, setCandidates] = useState(initialCandidates)
  const [sortBy, setSortBy] = useState('rank')
  const [shortlisted, setShortlisted] = useState(new Set())
  const [showShortlistOnly, setShowShortlistOnly] = useState(false)
  const [minScore, setMinScore] = useState(0)
  const [isReranking, setIsReranking] = useState(false)

  const toggleShortlist = useCallback((id) => {
    setShortlisted(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const handleRerank = useCallback(async (weights) => {
    setIsReranking(true)
    try {
      const res = await fetch(`${BACKEND}/api/rerank`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ candidates, weights, jd_analysis }),
      })
      if (!res.ok) throw new Error('Rerank failed')
      const data = await res.json()
      setCandidates(data.candidates)
    } catch (e) {
      console.error('Rerank error:', e)
    } finally {
      setIsReranking(false)
    }
  }, [candidates, jd_analysis])

  const sorted = useMemo(() => {
    let list = [...candidates]
    if (showShortlistOnly) list = list.filter(c => shortlisted.has(c.candidate_id))
    if (minScore > 0) list = list.filter(c => c.final_score * 100 >= minScore)
    switch (sortBy) {
      case 'skills':    list.sort((a, b) => (b.scores?.technical_skill_match ?? 0) - (a.scores?.technical_skill_match ?? 0)); break
      case 'career':    list.sort((a, b) => (b.scores?.career_trajectory ?? 0) - (a.scores?.career_trajectory ?? 0)); break
      case 'seniority': list.sort((a, b) => (b.scores?.seniority_alignment ?? 0) - (a.scores?.seniority_alignment ?? 0)); break
      case 'exp':       list.sort((a, b) => (b.total_years_experience ?? 0) - (a.total_years_experience ?? 0)); break
      case 'trust':     list.sort((a, b) => (b.trust_score ?? 1) - (a.trust_score ?? 1)); break
      default:          list.sort((a, b) => a.final_rank - b.final_rank)
    }
    return list
  }, [candidates, sortBy, showShortlistOnly, shortlisted, minScore])

  const discrepancyCount = candidates.filter(c => c.has_discrepancy).length

  return (
    <div className="pt-5">
      {/* ── Stat row ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {[
          { label: 'Analyzed',      value: meta?.total_candidates ?? candidates.length, suffix: '',  color: 'text-indigo-400',  icon: Users },
          { label: 'Shortlisted',   value: candidates.length,                           suffix: '',  color: 'text-emerald-400', icon: Award },
          { label: 'Top Score',     value: Math.round((candidates[0]?.final_score ?? 0) * 100), suffix: '%', color: 'text-amber-400', icon: TrendingUp },
          { label: 'Bias Audit',    value: bias_audit?.audit_passed ? 'Passed' : 'Review', suffix: '', color: bias_audit?.audit_passed ? 'text-emerald-400' : 'text-amber-400', icon: Shield },
        ].map(({ label, value, suffix, color, icon: Icon }, i) => (
          <motion.div key={label} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
            className="bg-[#161b27] border border-[#2a3347] rounded-xl p-3.5">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Icon size={12} className={color} />
              <span className="text-[11px] text-slate-500">{label}</span>
            </div>
            <div className={`text-xl font-bold ${color} tabular-nums`}>
              {typeof value === 'number' ? <><AnimatedNumber value={value} />{suffix}</> : value}
            </div>
          </motion.div>
        ))}
      </div>

      {/* ── Meta badges ── */}
      <div className="flex flex-wrap gap-2 mb-4">
        {meta?.cross_encoder_used && (
          <div className="flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-lg bg-violet-500/10 border border-violet-500/20 text-violet-300">
            <Cpu size={10} /> Cross-Encoder Active
          </div>
        )}
        {meta?.anonymous_mode && (
          <div className="flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-lg bg-slate-500/10 border border-slate-500/20 text-slate-300">
            <EyeOff size={10} /> Anonymous Mode
          </div>
        )}
        {discrepancyCount > 0 && (
          <div className="flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-lg bg-orange-500/10 border border-orange-500/20 text-orange-300">
            <AlertTriangle size={10} /> {discrepancyCount} Timeline Discrepancies
          </div>
        )}
        {meta?.cache_entries > 0 && (
          <div className="flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300">
            <CheckCircle2 size={10} /> {meta.cache_entries} Embeddings Cached
          </div>
        )}
      </div>

      {/* ── JD bar ── */}
      {jd_analysis && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }}
          className="bg-[#161b27] border border-[#2a3347] rounded-xl px-4 py-3 mb-4 flex flex-wrap gap-3 items-center">
          <div className="flex items-center gap-3 flex-wrap flex-1 min-w-0">
            <div>
              <div className="text-[10px] text-slate-500 uppercase tracking-wider">Role</div>
              <div className="text-sm font-semibold text-white leading-tight">{jd_analysis.role_title}</div>
            </div>
            <div className="w-px h-7 bg-[#2a3347] hidden sm:block" />
            <div>
              <div className="text-[10px] text-slate-500 uppercase tracking-wider">Level</div>
              <div className="text-sm font-medium text-indigo-300 capitalize">{jd_analysis.seniority_level}</div>
            </div>
            <div className="w-px h-7 bg-[#2a3347] hidden sm:block" />
            <div className="flex-1 min-w-0">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Required Skills</div>
              <div className="flex flex-wrap gap-1">
                {(jd_analysis.required_skills || []).slice(0, 8).map(s => (
                  <span key={s} className="text-[10px] px-1.5 py-0.5 rounded bg-[#1e2535] border border-[#2a3347] text-slate-300">{s}</span>
                ))}
              </div>
            </div>
          </div>
          <button onClick={() => downloadCSV(candidates)}
            className="flex-shrink-0 flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition-colors">
            <Download size={12} /> Export CSV
          </button>
        </motion.div>
      )}

      {/* ── Main grid ── */}
      <div className="grid lg:grid-cols-3 gap-5">
        {/* Candidate list */}
        <div className="lg:col-span-2">
          {/* Toolbar */}
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <div className="flex items-center gap-1.5 bg-[#161b27] border border-[#2a3347] rounded-lg px-2 py-1.5">
              <SortAsc size={12} className="text-slate-500" />
              <select value={sortBy} onChange={e => setSortBy(e.target.value)}
                className="bg-transparent text-xs text-slate-300 focus:outline-none cursor-pointer">
                {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-1.5 bg-[#161b27] border border-[#2a3347] rounded-lg px-2 py-1.5">
              <Filter size={12} className="text-slate-500" />
              <select value={minScore} onChange={e => setMinScore(Number(e.target.value))}
                className="bg-transparent text-xs text-slate-300 focus:outline-none cursor-pointer">
                <option value={0}>All scores</option>
                <option value={30}>≥ 30%</option>
                <option value={40}>≥ 40%</option>
                <option value={50}>≥ 50%</option>
                <option value={60}>≥ 60%</option>
              </select>
            </div>
            <button onClick={() => setShowShortlistOnly(v => !v)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-all
                ${showShortlistOnly ? 'bg-amber-500/15 border-amber-500/30 text-amber-300' : 'bg-[#161b27] border-[#2a3347] text-slate-400 hover:text-slate-300'}`}>
              <Star size={11} className={showShortlistOnly ? 'fill-current' : ''} />
              Shortlist {shortlisted.size > 0 && `(${shortlisted.size})`}
            </button>
            {(sortBy !== 'rank' || minScore > 0 || showShortlistOnly) && (
              <button onClick={() => { setSortBy('rank'); setMinScore(0); setShowShortlistOnly(false) }}
                className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors">
                <X size={11} /> Clear
              </button>
            )}
            <span className="ml-auto text-xs text-slate-600">{sorted.length} candidates</span>
          </div>

          {/* Cards */}
          <div className="space-y-2.5">
            {sorted.length === 0
              ? <div className="text-center py-12 text-slate-500 text-sm">No candidates match the current filters.</div>
              : sorted.map((c, i) => (
                  <CandidateCard key={c.candidate_id} candidate={c} index={i}
                    shortlisted={shortlisted.has(c.candidate_id)} onToggleShortlist={toggleShortlist} />
                ))
            }
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <WeightSliders candidates={candidates} onRerank={handleRerank} isReranking={isReranking} />
          <DimensionChart candidates={candidates} />
          <BiasAudit audit={bias_audit} />
          {shortlisted.size > 0 && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              className="bg-amber-500/8 border border-amber-500/20 rounded-2xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <Star size={13} className="text-amber-400 fill-current" />
                <span className="text-sm font-semibold text-amber-300">Your Shortlist</span>
                <span className="ml-auto text-xs text-amber-400/70">{shortlisted.size} candidates</span>
              </div>
              <div className="space-y-1.5 mb-3">
                {candidates.filter(c => shortlisted.has(c.candidate_id)).map(c => (
                  <div key={c.candidate_id} className="flex items-center justify-between text-xs">
                    <span className="text-slate-300">{c.name}</span>
                    <span className="text-amber-400 font-mono">{Math.round(c.final_score * 100)}%</span>
                  </div>
                ))}
              </div>
              <button onClick={() => downloadCSV(candidates.filter(c => shortlisted.has(c.candidate_id)), 'shortlist.csv')}
                className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 text-xs font-medium transition-colors border border-amber-500/20">
                <Download size={11} /> Export shortlist
              </button>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  )
}
