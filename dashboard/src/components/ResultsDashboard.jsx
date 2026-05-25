import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Users, TrendingUp, Award, Download, ChevronDown, ChevronUp,
  Shield, SortAsc, Star, StarOff, Filter, X, Briefcase, AlertTriangle
} from 'lucide-react'
import ScoreBar from './ScoreBar'
import ScoreRadar from './ScoreRadar'
import DimensionChart from './DimensionChart'
import BiasAudit from './BiasAudit'
import AnimatedNumber from './AnimatedNumber'

// ── Constants ────────────────────────────────────────────────────────────────

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
  { value: 'rank',     label: 'Best Match' },
  { value: 'skills',   label: 'Tech Skills' },
  { value: 'career',   label: 'Career Traj.' },
  { value: 'seniority',label: 'Seniority Fit' },
  { value: 'exp',      label: 'Experience' },
]

// ── Helpers ──────────────────────────────────────────────────────────────────

function downloadCSV(candidates) {
  const rows = candidates.map(c => ({
    rank: c.final_rank,
    name: c.name,
    title: c.current_title,
    years_exp: c.total_years_experience,
    final_score: (c.final_score * 100).toFixed(1) + '%',
    tech_skills: ((c.scores?.technical_skill_match ?? 0) * 100).toFixed(1) + '%',
    career_traj: ((c.scores?.career_trajectory ?? 0) * 100).toFixed(1) + '%',
    domain_depth: ((c.scores?.domain_depth ?? 0) * 100).toFixed(1) + '%',
    seniority_fit: ((c.scores?.seniority_alignment ?? 0) * 100).toFixed(1) + '%',
    behavioral: ((c.scores?.behavioral_signals ?? 0) * 100).toFixed(1) + '%',
    culture_fit: ((c.scores?.culture_soft_fit ?? 0) * 100).toFixed(1) + '%',
    risk: ((c.scores?.risk_penalty ?? 0) * 100).toFixed(1) + '%',
    top_skills: c.top_skills,
    location: c.location,
    explanation: c.explanation,
  }))
  const headers = Object.keys(rows[0]).join(',')
  const lines = rows.map(r => Object.values(r).map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(','))
  const blob = new Blob([[headers, ...lines].join('\n')], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'ranked_candidates.csv'
  a.click()
}

// ── Score ring ───────────────────────────────────────────────────────────────

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

// ── Missing skills badge ─────────────────────────────────────────────────────

function MissingSkills({ explanation, requiredSkills, candidateSkills }) {
  // Parse missing skills from explanation text
  const missing = []
  if (explanation) {
    const m = explanation.match(/[Mm]issing[:\s]+([^.]+)/)
    if (m) {
      m[1].split(',').forEach(s => {
        const t = s.trim().replace(/^missing:\s*/i, '')
        if (t && t.length < 40) missing.push(t)
      })
    }
  }
  if (missing.length === 0) return null
  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {missing.slice(0, 4).map(s => (
        <span key={s} className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/8 border border-red-500/15 text-red-400/80">
          − {s}
        </span>
      ))}
    </div>
  )
}

// ── Candidate card ───────────────────────────────────────────────────────────

const HIRE_REC = {
  strong_yes: { label: 'Strong Yes', cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25' },
  yes:        { label: 'Yes',        cls: 'bg-teal-500/15 text-teal-300 border-teal-500/25' },
  maybe:      { label: 'Maybe',      cls: 'bg-amber-500/15 text-amber-300 border-amber-500/25' },
  no:         { label: 'No',         cls: 'bg-red-500/15 text-red-300 border-red-500/25' },
}

function CandidateCard({ candidate, index, shortlisted, onToggleShortlist, requiredSkills }) {
  const [expanded, setExpanded] = useState(index < 2)
  const rank = candidate.final_rank
  const style = RANK_STYLES[rank] || { ring: '', bg: 'from-transparent', badge: 'bg-[#1e2535] text-slate-400 border-[#2a3347]', label: null }
  const dims = DIM_META.map(d => ({ ...d, value: candidate.scores?.[d.key] ?? 0 }))
  const riskScore = candidate.scores?.risk_penalty ?? 0
  const hasRisk = riskScore > 0.25

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.04, 0.4), duration: 0.3 }}
      className={`rounded-2xl border border-[#2a3347] ${style.ring} bg-gradient-to-br ${style.bg} to-transparent overflow-hidden`}
    >
      {/* Header */}
      <div className="p-4 flex items-center gap-3">
        {/* Rank */}
        <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold border ${style.badge}`}>
          {rank}
        </div>

        {/* Name + title */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-white text-sm leading-tight">{candidate.name}</span>
            {style.label && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium border ${style.badge}`}>
                {style.label}
              </span>
            )}
            {hasRisk && (
              <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400">
                <AlertTriangle size={9} /> risk
              </span>
            )}
          </div>
          <div className="text-xs text-slate-400 mt-0.5 truncate">
            {[candidate.current_title, candidate.total_years_experience > 0 && `${candidate.total_years_experience}y`, candidate.location]
              .filter(Boolean).join(' · ')}
          </div>
        </div>

        {/* Score ring */}
        <ScoreRing score={candidate.final_score} />

        {/* Shortlist toggle */}
        <button onClick={() => onToggleShortlist(candidate.candidate_id)}
          title={shortlisted ? 'Remove from shortlist' : 'Add to shortlist'}
          className={`flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center transition-all
            ${shortlisted ? 'bg-amber-500/15 text-amber-400 border border-amber-500/25' : 'bg-[#1e2535] text-slate-600 hover:text-slate-400 border border-[#2a3347]'}`}>
          {shortlisted ? <Star size={12} fill="currentColor" /> : <Star size={12} />}
        </button>

        {/* Expand */}
        <button onClick={() => setExpanded(e => !e)}
          className="flex-shrink-0 w-7 h-7 rounded-lg bg-[#1e2535] hover:bg-[#2a3347] flex items-center justify-center transition-colors text-slate-500 hover:text-slate-300 border border-[#2a3347]">
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      {/* Score bars */}
      <div className="px-4 pb-3 grid grid-cols-3 gap-x-5 gap-y-2">
        {dims.map(d => (
          <ScoreBar key={d.key} label={d.short} value={d.value} color={d.color} />
        ))}
      </div>

      {/* Skills + missing */}
      <div className="px-4 pb-3">
        {candidate.top_skills && (
          <div className="flex flex-wrap gap-1">
            {candidate.top_skills.split(',').slice(0, 8).map(s => s.trim()).filter(Boolean).map(s => (
              <span key={s} className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/15 text-indigo-300">
                {s}
              </span>
            ))}
          </div>
        )}
        <MissingSkills explanation={candidate.explanation} />
      </div>

      {/* Expanded */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-[#2a3347]/50"
          >
            <div className="p-4 grid md:grid-cols-2 gap-5">
              {/* Left: radar + score table */}
              <div>
                <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">Dimension Breakdown</div>
                <ScoreRadar dims={dims} />
                <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1">
                  {[...dims, { key: 'risk_penalty', label: 'Risk Penalty', short: 'Risk', color: '#ef4444', value: candidate.scores?.risk_penalty ?? 0 }].map(d => (
                    <div key={d.key} className="flex items-center justify-between text-[11px]">
                      <span className="text-slate-500">{d.label}</span>
                      <span className="font-mono font-semibold tabular-nums" style={{ color: d.color }}>
                        {d.key === 'risk_penalty' ? `−${Math.round(d.value * 100)}%` : `${Math.round(d.value * 100)}%`}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right: assessment + why hire + key signals */}
              <div className="space-y-3">
                {/* Hire recommendation */}
                {candidate.hire_recommendation && (() => {
                  const rec = HIRE_REC[candidate.hire_recommendation] || HIRE_REC.maybe
                  return (
                    <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-semibold ${rec.cls}`}>
                      Recommendation: {rec.label}
                      {candidate.confidence > 0 && (
                        <span className="opacity-60 font-normal">· {Math.round(candidate.confidence * 100)}% confidence</span>
                      )}
                    </div>
                  )
                })()}

                {/* Why hire */}
                {candidate.why_hire && (
                  <div className="bg-indigo-500/8 rounded-xl p-3 border border-indigo-500/15">
                    <div className="text-[10px] font-semibold text-indigo-400 uppercase tracking-wider mb-1">Why Hire</div>
                    <p className="text-[12px] text-slate-200 leading-relaxed font-medium">{candidate.why_hire}</p>
                  </div>
                )}

                {/* Recruiter note */}
                {candidate.explanation && (
                  <div className="bg-[#0f1117] rounded-xl p-3 border-l-2 border-indigo-500/50">
                    <div className="text-[10px] font-semibold text-indigo-400 uppercase tracking-wider mb-1.5">Recruiter Assessment</div>
                    <p className="text-[12px] text-slate-300 leading-relaxed">{candidate.explanation}</p>
                  </div>
                )}

                {/* Key strength / concern */}
                <div className="grid grid-cols-2 gap-2">
                  {candidate.key_strength && (
                    <div className="bg-emerald-500/6 rounded-lg p-2.5 border border-emerald-500/15">
                      <div className="text-[9px] font-semibold text-emerald-500 uppercase tracking-wider mb-1">Key Strength</div>
                      <div className="text-[11px] text-slate-300 leading-snug">{candidate.key_strength}</div>
                    </div>
                  )}
                  {candidate.key_concern && candidate.key_concern !== 'None identified' && (
                    <div className="bg-amber-500/6 rounded-lg p-2.5 border border-amber-500/15">
                      <div className="text-[9px] font-semibold text-amber-500 uppercase tracking-wider mb-1">Watch Out</div>
                      <div className="text-[11px] text-slate-300 leading-snug">{candidate.key_concern}</div>
                    </div>
                  )}
                </div>

                {/* Work history */}
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

// ── Main dashboard ───────────────────────────────────────────────────────────

export default function ResultsDashboard({ results, onReset }) {
  const { candidates, jd_analysis, bias_audit, meta } = results
  const [sortBy, setSortBy] = useState('rank')
  const [shortlisted, setShortlisted] = useState(new Set())
  const [showShortlistOnly, setShowShortlistOnly] = useState(false)
  const [minScore, setMinScore] = useState(0)

  const toggleShortlist = (id) => {
    setShortlisted(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const sorted = useMemo(() => {
    let list = [...candidates]
    if (showShortlistOnly) list = list.filter(c => shortlisted.has(c.candidate_id))
    if (minScore > 0) list = list.filter(c => c.final_score * 100 >= minScore)
    switch (sortBy) {
      case 'skills':   list.sort((a, b) => (b.scores?.technical_skill_match ?? 0) - (a.scores?.technical_skill_match ?? 0)); break
      case 'career':   list.sort((a, b) => (b.scores?.career_trajectory ?? 0) - (a.scores?.career_trajectory ?? 0)); break
      case 'seniority':list.sort((a, b) => (b.scores?.seniority_alignment ?? 0) - (a.scores?.seniority_alignment ?? 0)); break
      case 'exp':      list.sort((a, b) => (b.total_years_experience ?? 0) - (a.total_years_experience ?? 0)); break
      default:         list.sort((a, b) => a.final_rank - b.final_rank)
    }
    return list
  }, [candidates, sortBy, showShortlistOnly, shortlisted, minScore])

  return (
    <div className="pt-5">

      {/* ── Stat row ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {[
          { label: 'Analyzed',    value: meta?.total_candidates ?? candidates.length, suffix: '',  color: 'text-indigo-400',  icon: Users },
          { label: 'Shortlisted', value: candidates.length,                           suffix: '',  color: 'text-emerald-400', icon: Award },
          { label: 'Top Score',   value: Math.round((candidates[0]?.final_score ?? 0) * 100), suffix: '%', color: 'text-amber-400', icon: TrendingUp },
          { label: 'Bias Audit',  value: bias_audit?.audit_passed ? 'Passed' : 'Review', suffix: '', color: bias_audit?.audit_passed ? 'text-emerald-400' : 'text-amber-400', icon: Shield },
        ].map(({ label, value, suffix, color, icon: Icon }, i) => (
          <motion.div key={label}
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
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

      {/* ── JD + export bar ── */}
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
            <Download size={12} />
            Export CSV
          </button>
        </motion.div>
      )}

      {/* ── Main grid ── */}
      <div className="grid lg:grid-cols-3 gap-5">

        {/* Candidate list */}
        <div className="lg:col-span-2">

          {/* Filter/sort toolbar */}
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            {/* Sort */}
            <div className="flex items-center gap-1.5 bg-[#161b27] border border-[#2a3347] rounded-lg px-2 py-1.5">
              <SortAsc size={12} className="text-slate-500" />
              <select value={sortBy} onChange={e => setSortBy(e.target.value)}
                className="bg-transparent text-xs text-slate-300 focus:outline-none cursor-pointer">
                {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>

            {/* Min score filter */}
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

            {/* Shortlist toggle */}
            <button onClick={() => setShowShortlistOnly(v => !v)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-all
                ${showShortlistOnly
                  ? 'bg-amber-500/15 border-amber-500/30 text-amber-300'
                  : 'bg-[#161b27] border-[#2a3347] text-slate-400 hover:text-slate-300'}`}>
              <Star size={11} className={showShortlistOnly ? 'fill-current' : ''} />
              Shortlist {shortlisted.size > 0 && `(${shortlisted.size})`}
            </button>

            {/* Clear filters */}
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
            {sorted.length === 0 ? (
              <div className="text-center py-12 text-slate-500 text-sm">
                No candidates match the current filters.
              </div>
            ) : (
              sorted.map((c, i) => (
                <CandidateCard
                  key={c.candidate_id}
                  candidate={c}
                  index={i}
                  shortlisted={shortlisted.has(c.candidate_id)}
                  onToggleShortlist={toggleShortlist}
                  requiredSkills={jd_analysis?.required_skills || []}
                />
              ))
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <DimensionChart candidates={candidates} />
          <BiasAudit audit={bias_audit} />

          {/* Shortlist export */}
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
              <button
                onClick={() => downloadCSV(candidates.filter(c => shortlisted.has(c.candidate_id)))}
                className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 text-xs font-medium transition-colors border border-amber-500/20">
                <Download size={11} />
                Export shortlist
              </button>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  )
}
