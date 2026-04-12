import { useState, useEffect } from 'react'
import './LoadingState.css'

const STAGES = [
  { label: 'Uploading document...', pct: 10 },
  { label: 'Scanning document layout & fonts...', pct: 25 },
  { label: 'Checking security features...', pct: 40 },
  { label: 'Extracting identity fields...', pct: 58 },
  { label: 'Running cross-document match...', pct: 72 },
  { label: 'Evaluating compliance flags...', pct: 85 },
  { label: 'Generating notary report...', pct: 95 },
]

export default function LoadingState() {
  const [stage, setStage] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setStage(s => Math.min(s + 1, STAGES.length - 1))
    }, 1600)
    return () => clearInterval(interval)
  }, [])

  const current = STAGES[stage]

  return (
    <div className="loading-state fade-up">
      <div className="loading-inner">
        <div className="scan-frame">
          <div className="scan-corners">
            <div className="corner tl" /><div className="corner tr" />
            <div className="corner bl" /><div className="corner br" />
          </div>
          <div className="scan-line" />
          <div className="scan-icon">🪪</div>
        </div>

        <div className="loading-label">{current.label}</div>

        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${current.pct}%` }} />
        </div>
        <div className="progress-pct">{current.pct}%</div>

        <div className="stage-dots">
          {STAGES.map((_, i) => (
            <div key={i} className={`dot ${i <= stage ? 'done' : ''} ${i === stage ? 'active' : ''}`} />
          ))}
        </div>

        <div className="loading-sub">Running all 4 levels · Powered by Claude Vision</div>
      </div>
    </div>
  )
}
