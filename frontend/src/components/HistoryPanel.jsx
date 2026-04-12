import { useState, useEffect } from 'react'
import './HistoryPanel.css'

export default function HistoryPanel({ onLoadResult }) {
  const [rows, setRows] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState(null)

  useEffect(() => {
    Promise.all([
      fetch('/api/history').then(r => r.json()),
      fetch('/api/stats').then(r => r.json())
    ]).then(([h, s]) => { setRows(h); setStats(s); setLoading(false); }).catch(() => setLoading(false))
  }, [])

  const deleteRow = async (id, e) => {
    e.stopPropagation()
    await fetch(`/api/history/${id}`, { method: 'DELETE' })
    setRows(prev => prev.filter(r => r.id !== id))
  }

  const filtered = filter ? rows.filter(r => r.overall_verdict === filter) : rows

  const riskColor = { LOW: 'var(--green)', MEDIUM: 'var(--warn)', HIGH: 'var(--accent2)', CRITICAL: 'var(--accent2)' }
  const verdictIcon = { PASS: '✅', FAIL: '🚫', WARN: '⚠️' }

  if (loading) return <div className="history-loading">Loading history...</div>

  return (
    <div className="history-panel fade-up">
      {stats && (
        <div className="history-stats">
          <div className="stat-box"><div className="stat-val blue">{stats.total}</div><div className="stat-lbl">TOTAL</div></div>
          <div className="stat-box"><div className="stat-val green">{stats.passed}</div><div className="stat-lbl">PASSED</div></div>
          <div className="stat-box"><div className="stat-val warn">{stats.warned}</div><div className="stat-lbl">WARNED</div></div>
          <div className="stat-box"><div className="stat-val red">{stats.failed}</div><div className="stat-lbl">FAILED</div></div>
        </div>
      )}

      <div className="history-filters">
        {[null, 'PASS', 'WARN', 'FAIL'].map(f => (
          <button key={String(f)} className={`filter-btn ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)}>
            {f || 'ALL'}
          </button>
        ))}
        <span className="history-count">{filtered.length} records</span>
      </div>

      {filtered.length === 0 ? (
        <div className="history-empty">
          <div style={{fontSize:'2rem',marginBottom:'0.5rem'}}>🔍</div>
          <div>No verifications yet. Run your first one on the Verify tab.</div>
        </div>
      ) : (
        <div className="history-table-wrap">
          <div className="history-table-head">
            <span>ID</span><span>NAME</span><span>STATE</span>
            <span>VERDICT</span><span>RISK</span><span>REC.</span>
            <span>EXPIRY</span><span>TIME</span><span></span>
          </div>
          {filtered.map(r => (
            <div key={r.id} className="history-row" onClick={() => onLoadResult && alert('Load from DB not yet implemented — use Demo or run a new verification')}>
              <span className="hist-id">{r.id}</span>
              <span className="hist-name">{r.extracted_name || '—'}</span>
              <span>{r.extracted_state || '—'}</span>
              <span>
                <span className={`verdict-chip vc-${r.overall_verdict}`}>
                  {verdictIcon[r.overall_verdict]} {r.overall_verdict}
                </span>
              </span>
              <span style={{ color: riskColor[r.risk_level] || 'var(--muted)', fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
                {r.risk_level || '—'}
              </span>
              <span className="hist-rec">{(r.recommendation || '').replace(/_/g,' ')}</span>
              <span className={`hist-exp ${r.expiration === 'EXPIRED' ? 'exp-bad' : r.expiration === 'EXPIRING_SOON' ? 'exp-warn' : ''}`}>
                {r.expiration || '—'}
              </span>
              <span className="hist-ms">{r.processing_ms}ms</span>
              <span>
                <button className="del-btn" onClick={e => deleteRow(r.id, e)} title="Delete">✕</button>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
