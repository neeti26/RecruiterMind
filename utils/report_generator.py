"""
HTML Report Generator
Produces a beautiful, interactive HTML report with:
- Ranked candidate table with score breakdowns
- Radar charts per candidate
- Score distribution plots
- Bias audit summary
"""

import json
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RecruiterMind — Candidate Ranking Report</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #0f172a; color: #e2e8f0; line-height: 1.6; }}
  .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
             padding: 2rem; border-bottom: 1px solid #334155; }}
  .header h1 {{ font-size: 2rem; font-weight: 700; color: #60a5fa; }}
  .header .subtitle {{ color: #94a3b8; margin-top: 0.5rem; }}
  .meta {{ display: flex; gap: 2rem; margin-top: 1rem; flex-wrap: wrap; }}
  .meta-item {{ background: #1e293b; padding: 0.5rem 1rem; border-radius: 8px;
                border: 1px solid #334155; }}
  .meta-item span {{ color: #60a5fa; font-weight: 600; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 2rem; }}
  .section {{ margin-bottom: 3rem; }}
  .section-title {{ font-size: 1.25rem; font-weight: 600; color: #60a5fa;
                    margin-bottom: 1rem; padding-bottom: 0.5rem;
                    border-bottom: 1px solid #334155; }}
  .candidate-card {{ background: #1e293b; border: 1px solid #334155;
                     border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem;
                     transition: border-color 0.2s; }}
  .candidate-card:hover {{ border-color: #60a5fa; }}
  .candidate-card.rank-1 {{ border-color: #fbbf24; background: #1c2a1a; }}
  .candidate-card.rank-2 {{ border-color: #94a3b8; }}
  .candidate-card.rank-3 {{ border-color: #cd7c2f; }}
  .card-header {{ display: flex; justify-content: space-between; align-items: flex-start;
                  margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem; }}
  .candidate-name {{ font-size: 1.1rem; font-weight: 700; }}
  .rank-badge {{ background: #334155; padding: 0.25rem 0.75rem; border-radius: 20px;
                 font-weight: 700; font-size: 0.9rem; }}
  .rank-badge.gold {{ background: #92400e; color: #fbbf24; }}
  .rank-badge.silver {{ background: #374151; color: #d1d5db; }}
  .rank-badge.bronze {{ background: #431407; color: #cd7c2f; }}
  .candidate-title {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 0.5rem; }}
  .score-bar-container {{ margin: 0.75rem 0; }}
  .score-label {{ display: flex; justify-content: space-between; font-size: 0.8rem;
                  color: #94a3b8; margin-bottom: 0.25rem; }}
  .score-bar {{ height: 6px; background: #334155; border-radius: 3px; overflow: hidden; }}
  .score-fill {{ height: 100%; border-radius: 3px; transition: width 0.3s; }}
  .fill-blue {{ background: linear-gradient(90deg, #3b82f6, #60a5fa); }}
  .fill-green {{ background: linear-gradient(90deg, #10b981, #34d399); }}
  .fill-purple {{ background: linear-gradient(90deg, #8b5cf6, #a78bfa); }}
  .fill-orange {{ background: linear-gradient(90deg, #f59e0b, #fbbf24); }}
  .fill-pink {{ background: linear-gradient(90deg, #ec4899, #f472b6); }}
  .fill-teal {{ background: linear-gradient(90deg, #14b8a6, #2dd4bf); }}
  .fill-red {{ background: linear-gradient(90deg, #ef4444, #f87171); }}
  .final-score {{ font-size: 1.5rem; font-weight: 700; color: #60a5fa; }}
  .explanation {{ background: #0f172a; border-left: 3px solid #60a5fa;
                  padding: 0.75rem 1rem; border-radius: 0 8px 8px 0;
                  font-size: 0.9rem; color: #cbd5e1; margin-top: 0.75rem; }}
  .skills-list {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.5rem; }}
  .skill-tag {{ background: #1e3a5f; color: #93c5fd; padding: 0.2rem 0.6rem;
                border-radius: 12px; font-size: 0.75rem; border: 1px solid #1d4ed8; }}
  .bias-audit {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px;
                 padding: 1.5rem; }}
  .audit-pass {{ color: #34d399; font-weight: 600; }}
  .audit-warn {{ color: #fbbf24; font-weight: 600; }}
  .chart-container {{ background: #1e293b; border: 1px solid #334155;
                      border-radius: 12px; padding: 1rem; margin-bottom: 1rem; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
  @media (max-width: 768px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
  .footer {{ text-align: center; padding: 2rem; color: #475569; font-size: 0.85rem;
             border-top: 1px solid #334155; margin-top: 3rem; }}
</style>
</head>
<body>

<div class="header">
  <div style="max-width: 1400px; margin: 0 auto;">
    <h1>🧠 RecruiterMind</h1>
    <div class="subtitle">AI-Powered Candidate Ranking — Hack2Skill India Runs 2026</div>
    <div class="meta">
      <div class="meta-item">Role: <span>{role_title}</span></div>
      <div class="meta-item">Seniority: <span>{seniority_level}</span></div>
      <div class="meta-item">Candidates Analyzed: <span>{total_candidates}</span></div>
      <div class="meta-item">Shortlisted: <span>{shortlisted}</span></div>
      <div class="meta-item">Generated: <span>{timestamp}</span></div>
    </div>
  </div>
</div>

<div class="container">

  <!-- Score Distribution Chart -->
  <div class="section">
    <div class="section-title">📊 Score Distribution</div>
    <div class="grid-2">
      <div class="chart-container">
        <div id="score-dist-chart"></div>
      </div>
      <div class="chart-container">
        <div id="dimension-avg-chart"></div>
      </div>
    </div>
  </div>

  <!-- Top Candidates -->
  <div class="section">
    <div class="section-title">🏆 Ranked Candidates</div>
    {candidate_cards}
  </div>

  <!-- Bias Audit -->
  <div class="section">
    <div class="section-title">⚖️ Bias Audit</div>
    <div class="bias-audit">
      <div style="margin-bottom: 0.5rem;">
        Status: {bias_status}
      </div>
      {bias_flags_html}
      <div style="margin-top: 1rem; color: #94a3b8; font-size: 0.85rem;">
        RecruiterMind actively neutralizes name-based and demographic bias.
        Candidates are evaluated purely on skills, experience, and trajectory.
      </div>
    </div>
  </div>

</div>

<div class="footer">
  RecruiterMind — Built for Hack2Skill India Runs 2026 Data & AI Challenge<br>
  Architecture: Hybrid Retrieval (FAISS + BM25) → 7-Dimension Scoring → LLM Tournament Reranking → Plackett-Luce Aggregation
</div>

<script>
const candidates = {candidates_json};

// Score distribution
const finalScores = candidates.map(c => c.final_score * 100);
const names = candidates.map(c => c.name.split(' ')[0] + ' #' + c.final_rank);

Plotly.newPlot('score-dist-chart', [{{
  x: names,
  y: finalScores,
  type: 'bar',
  marker: {{
    color: finalScores,
    colorscale: 'Blues',
    showscale: false
  }},
  text: finalScores.map(s => s.toFixed(1) + '%'),
  textposition: 'outside',
}}], {{
  title: {{ text: 'Final Scores by Candidate', font: {{ color: '#e2e8f0' }} }},
  paper_bgcolor: '#1e293b',
  plot_bgcolor: '#1e293b',
  font: {{ color: '#94a3b8' }},
  xaxis: {{ tickangle: -45 }},
  yaxis: {{ title: 'Score (%)', range: [0, 110] }},
  margin: {{ t: 50, b: 100 }}
}});

// Dimension averages
const dims = ['technical_skill_match', 'career_trajectory', 'domain_depth',
              'seniority_alignment', 'behavioral_signals', 'culture_soft_fit'];
const dimLabels = ['Tech Skills', 'Career Traj.', 'Domain Depth',
                   'Seniority', 'Behavioral', 'Culture Fit'];
const dimAvgs = dims.map(d => {{
  const vals = candidates.map(c => (c.scores[d] || 0) * 100);
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}});

Plotly.newPlot('dimension-avg-chart', [{{
  type: 'scatterpolar',
  r: dimAvgs,
  theta: dimLabels,
  fill: 'toself',
  fillcolor: 'rgba(96, 165, 250, 0.2)',
  line: {{ color: '#60a5fa' }},
  name: 'Avg Score'
}}], {{
  title: {{ text: 'Average Dimension Scores (Top 20)', font: {{ color: '#e2e8f0' }} }},
  paper_bgcolor: '#1e293b',
  polar: {{
    bgcolor: '#1e293b',
    radialaxis: {{ visible: true, range: [0, 100], color: '#475569' }},
    angularaxis: {{ color: '#94a3b8' }}
  }},
  font: {{ color: '#94a3b8' }},
  margin: {{ t: 50 }}
}});
</script>
</body>
</html>"""

CANDIDATE_CARD_TEMPLATE = """
<div class="candidate-card {rank_class}">
  <div class="card-header">
    <div>
      <div class="candidate-name">{name}</div>
      <div class="candidate-title">{title} · {years} years exp · {location}</div>
    </div>
    <div style="display: flex; align-items: center; gap: 1rem;">
      <div class="final-score">{final_score_pct}</div>
      <div class="rank-badge {badge_class}">#{rank}</div>
    </div>
  </div>

  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem 2rem;">
    <div class="score-bar-container">
      <div class="score-label"><span>Technical Skills</span><span>{skill_score}</span></div>
      <div class="score-bar"><div class="score-fill fill-blue" style="width:{skill_pct}%"></div></div>
    </div>
    <div class="score-bar-container">
      <div class="score-label"><span>Career Trajectory</span><span>{traj_score}</span></div>
      <div class="score-bar"><div class="score-fill fill-green" style="width:{traj_pct}%"></div></div>
    </div>
    <div class="score-bar-container">
      <div class="score-label"><span>Domain Depth</span><span>{domain_score}</span></div>
      <div class="score-bar"><div class="score-fill fill-purple" style="width:{domain_pct}%"></div></div>
    </div>
    <div class="score-bar-container">
      <div class="score-label"><span>Seniority Alignment</span><span>{seniority_score}</span></div>
      <div class="score-bar"><div class="score-fill fill-orange" style="width:{seniority_pct}%"></div></div>
    </div>
    <div class="score-bar-container">
      <div class="score-label"><span>Behavioral Signals</span><span>{behavioral_score}</span></div>
      <div class="score-bar"><div class="score-fill fill-pink" style="width:{behavioral_pct}%"></div></div>
    </div>
    <div class="score-bar-container">
      <div class="score-label"><span>Culture Fit</span><span>{culture_score}</span></div>
      <div class="score-bar"><div class="score-fill fill-teal" style="width:{culture_pct}%"></div></div>
    </div>
  </div>

  <div class="skills-list">
    {skill_tags}
  </div>

  {explanation_html}
</div>"""


def generate_html_report(
    candidates: List,
    jd_analysis,
    bias_audit,
    output_path: str,
    top_n: int = 20,
):
    """Generate a full HTML report."""
    try:
        cards_html = ""
        candidates_data = []

        for i, candidate in enumerate(candidates[:top_n]):
            rank = i + 1
            scores = candidate.scores

            rank_class = ""
            badge_class = ""
            if rank == 1:
                rank_class = "rank-1"
                badge_class = "gold"
            elif rank == 2:
                rank_class = "rank-2"
                badge_class = "silver"
            elif rank == 3:
                rank_class = "rank-3"
                badge_class = "bronze"

            skill_tags = "".join(
                f'<span class="skill-tag">{s}</span>'
                for s in candidate.skills[:8]
            )

            explanation_html = ""
            if candidate.explanation:
                explanation_html = f'<div class="explanation">💬 {candidate.explanation}</div>'

            def fmt_score(s):
                return f"{s:.0%}"

            def fmt_pct(s):
                return f"{min(100, s * 100):.0f}"

            cards_html += CANDIDATE_CARD_TEMPLATE.format(
                rank_class=rank_class,
                badge_class=badge_class,
                name=candidate.name,
                title=candidate.current_title or "N/A",
                years=f"{candidate.total_years_experience:.0f}",
                location=candidate.location or "N/A",
                final_score_pct=f"{candidate.final_score:.0%}",
                rank=rank,
                skill_score=fmt_score(scores.get("technical_skill_match", 0)),
                skill_pct=fmt_pct(scores.get("technical_skill_match", 0)),
                traj_score=fmt_score(scores.get("career_trajectory", 0)),
                traj_pct=fmt_pct(scores.get("career_trajectory", 0)),
                domain_score=fmt_score(scores.get("domain_depth", 0)),
                domain_pct=fmt_pct(scores.get("domain_depth", 0)),
                seniority_score=fmt_score(scores.get("seniority_alignment", 0)),
                seniority_pct=fmt_pct(scores.get("seniority_alignment", 0)),
                behavioral_score=fmt_score(scores.get("behavioral_signals", 0)),
                behavioral_pct=fmt_pct(scores.get("behavioral_signals", 0)),
                culture_score=fmt_score(scores.get("culture_soft_fit", 0)),
                culture_pct=fmt_pct(scores.get("culture_soft_fit", 0)),
                skill_tags=skill_tags,
                explanation_html=explanation_html,
            )

            candidates_data.append({
                "name": candidate.name,
                "final_rank": rank,
                "final_score": round(candidate.final_score, 4),
                "scores": {k: round(v, 4) for k, v in scores.items()},
            })

        # Bias audit section
        if bias_audit and bias_audit.audit_passed:
            bias_status = '<span class="audit-pass">✅ PASSED — No significant bias detected</span>'
        else:
            bias_status = '<span class="audit-warn">⚠️ REVIEW RECOMMENDED</span>'

        bias_flags_html = ""
        if bias_audit and bias_audit.bias_flags:
            flags = "".join(f"<li>{f}</li>" for f in bias_audit.bias_flags)
            bias_flags_html = f'<ul style="color: #fbbf24; margin-top: 0.5rem;">{flags}</ul>'

        html = HTML_TEMPLATE.format(
            role_title=jd_analysis.role_title,
            seniority_level=jd_analysis.seniority_level,
            total_candidates=len(candidates),
            shortlisted=min(top_n, len(candidates)),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            candidate_cards=cards_html,
            bias_status=bias_status,
            bias_flags_html=bias_flags_html,
            candidates_json=json.dumps(candidates_data),
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"HTML report saved to {output_path}")

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise
