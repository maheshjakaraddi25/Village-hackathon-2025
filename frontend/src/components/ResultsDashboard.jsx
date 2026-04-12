import { useState } from 'react'
import './ResultsDashboard.css'

// ─── Shared primitives ────────────────────────────────────────────────────────

function VerdictBanner({ verdict, message }) {
  const map = {
    PASS: { cls: 'pass', icon: '✅' },
    FAIL: { cls: 'fail', icon: '🚫' },
    WARN: { cls: 'warn', icon: '⚠️' },
    PROCEED: { cls: 'pass', icon: '✅' },
    HOLD: { cls: 'warn', icon: '⚠️' },
    REJECT: { cls: 'fail', icon: '🚫' },
  }
  const d = map[verdict] || map.WARN
  return (
    <div className={`verdict-banner ${d.cls}`}>
      <span className="verdict-icon">{d.icon}</span>
      <span>{message}</span>
    </div>
  )
}

function FlagList({ flags }) {
  if (!flags?.length) return <div className="no-flags">✓ No issues detected</div>
  return (
    <div className="flag-list">
      {flags.map((f, i) => {
        const cls = f.severity === 'ERROR' ? 'err' : f.severity === 'WARN' ? 'warn' : 'ok'
        const icon = f.severity === 'ERROR' ? '🚫' : f.severity === 'WARN' ? '⚠️' : '✅'
        return (
          <div key={i} className={`flag-item ${cls}`}>
            <span className="flag-icon">{icon}</span>
            <div>
              <div className="flag-msg">{f.message}</div>
              {f.rule_citation && <div className="flag-cite">📋 {f.rule_citation}</div>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function ConfidenceBar({ label, value }) {
  const pct = Math.round((value || 0) * 100)
  const color = pct >= 70 ? 'var(--green)' : pct >= 40 ? 'var(--warn)' : 'var(--accent2)'
  return (
    <div className="conf-row">
      <div className="conf-label">{label.replace(/_/g, ' ')}</div>
      <div className="conf-bar-track">
        <div className="conf-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="conf-val" style={{ color }}>{pct}%</div>
    </div>
  )
}

function JsonBlock({ data, id }) {
  const [copied, setCopied] = useState(false)
  const str = JSON.stringify(data, null, 2)
  const copy = () => {
    navigator.clipboard.writeText(str).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }
  return (
    <div className="json-wrap">
      <button className="copy-btn" onClick={copy}>{copied ? '✓ COPIED' : 'COPY JSON'}</button>
      <pre className="json-block">{syntaxColor(str)}</pre>
    </div>
  )
}

function syntaxColor(str) {
  // Returns array of spans — simplified inline render
  return str
}

function SectionCard({ level, levelColor, title, rightLabel, rightColor, children }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="section-card">
      <div className="section-header" onClick={() => setOpen(o => !o)}>
        <div className="section-left">
          <div className="section-badge" style={{ background: `${levelColor}22`, color: levelColor, borderColor: `${levelColor}44` }}>{level}</div>
          <h3 className="section-title">{title}</h3>
        </div>
        <div className="section-right">
          {rightLabel && <span className="section-metric" style={{ color: rightColor || 'var(--muted)' }}>{rightLabel}</span>}
          <span className="chevron">{open ? '▲' : '▼'}</span>
        </div>
      </div>
      {open && <div className="section-body">{children}</div>}
    </div>
  )
}


// ─── Level panels ──────────────────────────────────────────────────────────────

function Level1Panel({ data }) {
  const score = Math.round((data.authenticity_score || 0) * 100)
  const scoreColor = score >= 70 ? 'var(--green)' : score >= 40 ? 'var(--warn)' : 'var(--accent2)'
  return (
    <SectionCard level="LV1" levelColor="#00e676" title="Document Authenticity" rightLabel={`${score}% AUTHENTIC`} rightColor={scoreColor}>
      <VerdictBanner verdict={data.verdict} message={data.verdict_message} />

      <div className="checks-grid">
        {(data.checks || []).map((c, i) => {
          const rcolor = c.result === 'PASS' ? 'var(--green)' : c.result === 'FAIL' ? 'var(--accent2)' : 'var(--warn)'
          const ricon = c.result === 'PASS' ? '✅' : c.result === 'FAIL' ? '🚫' : '⚠️'
          return (
            <div key={i} className="check-item">
              <div className="check-header">
                <span>{ricon}</span>
                <strong className="check-name">{c.check}</strong>
                <span className="check-result" style={{ color: rcolor }}>{c.result}</span>
              </div>
              <p className="check-detail">{c.detail}</p>
            </div>
          )
        })}
      </div>

      <FlagList flags={data.flags} />

      {data.suspicious_elements?.length > 0 && (
        <div className="suspicious-row">
          <span className="suspicious-label">🔎 Suspicious elements:</span>
          {data.suspicious_elements.map((s, i) => (
            <span key={i} className="suspicious-tag">{s}</span>
          ))}
        </div>
      )}
    </SectionCard>
  )
}

function Level2Panel({ data }) {
  const conf = Math.round((data.extraction_confidence || 0) * 100)
  const ef = data.extracted_fields || {}
  return (
    <SectionCard level="LV2" levelColor="#ffb400" title="Field Extraction & Structuring" rightLabel={`${conf}% OCR CONF`} rightColor={conf >= 70 ? 'var(--green)' : 'var(--warn)'}>
      <div className="fields-grid">
        {Object.entries(ef).filter(([, v]) => v != null).map(([k, v]) => (
          <div key={k} className="field-item">
            <div className="field-key">{k.replace(/_/g, ' ').toUpperCase()}</div>
            <div className="field-val">{v}</div>
          </div>
        ))}
      </div>

      <div className="conf-section">
        <div className="conf-section-title">Field Confidence Scores</div>
        {Object.entries(data.field_confidences || {}).map(([k, v]) => (
          <ConfidenceBar key={k} label={k} value={v} />
        ))}
      </div>

      {data.ocr_issues?.length > 0 && (
        <div className="ocr-issues">
          <span>⚠ OCR Issues: </span>
          {data.ocr_issues.join(' · ')}
        </div>
      )}

      <JsonBlock data={ef} id="lv2" />
    </SectionCard>
  )
}

function Level3Panel({ data }) {
  if (!data.cross_doc_available) {
    return (
      <SectionCard level="LV3" levelColor="#00e5ff" title="Cross-Document Identity Match" rightLabel="NO SECOND DOC" rightColor="var(--muted)">
        <div className="no-doc-msg">
          Upload a second supporting document (loan app, deed, utility bill) to enable cross-document analysis.
        </div>
      </SectionCard>
    )
  }

  const score = Math.round((data.overall_match_score || 0) * 100)
  const scoreColor = score >= 70 ? 'var(--green)' : score >= 40 ? 'var(--warn)' : 'var(--accent2)'

  return (
    <SectionCard level="LV3" levelColor="#00e5ff" title="Cross-Document Identity Match" rightLabel={`${score}% MATCH`} rightColor={scoreColor}>
      <VerdictBanner verdict={
        data.identity_consistency === 'CONSISTENT' ? 'PASS' :
        data.identity_consistency === 'INCONSISTENT' ? 'FAIL' : 'WARN'
      } message={`Identity Consistency: ${data.identity_consistency}`} />

      <div className="comparison-table">
        <div className="comp-header">
          <span>FIELD</span>
          <span>ID VALUE</span>
          <span>DOCUMENT VALUE</span>
          <span>CONFIDENCE</span>
          <span>STATUS</span>
        </div>
        {(data.comparisons || []).map((c, i) => {
          const flagColor = c.flag === 'MATCH' ? 'var(--green)' : c.flag === 'MISMATCH' ? 'var(--accent2)' : 'var(--warn)'
          return (
            <div key={i} className="comp-row">
              <span className="comp-field">{c.field}</span>
              <span className="comp-val">{c.id_value || '—'}</span>
              <span className="comp-val muted">{c.doc_value || '—'}</span>
              <span className="comp-conf">{Math.round(c.confidence * 100)}%</span>
              <span className="comp-flag" style={{ color: flagColor }}>{c.flag}</span>
            </div>
          )
        })}
      </div>

      <JsonBlock data={data} id="lv3" />
    </SectionCard>
  )
}

function Level4Panel({ data }) {
  const exp = data.expiration_status || {}
  const expColor = exp.status === 'VALID' ? 'var(--green)' : exp.status === 'EXPIRED' ? 'var(--accent2)' : 'var(--warn)'
  const expIcon = exp.status === 'VALID' ? '✅' : exp.status === 'EXPIRED' ? '🚫' : '⚠️'

  return (
    <SectionCard level="LV4" levelColor="#ff3d71" title="Expiration & Compliance" rightLabel={data.overall_recommendation} rightColor={data.overall_recommendation === 'PROCEED' ? 'var(--green)' : data.overall_recommendation === 'REJECT' ? 'var(--accent2)' : 'var(--warn)'}>
      <VerdictBanner verdict={data.overall_recommendation} message={`${data.overall_recommendation}: ${data.recommendation_detail}`} />

      <div className="expiry-card">
        <span className="expiry-icon">{expIcon}</span>
        <div>
          <div className="expiry-title">Document Expiration</div>
          <div className="expiry-status" style={{ color: expColor }}>
            {exp.status}
            {exp.days_until_expiry != null && ` · ${exp.days_until_expiry > 0 ? exp.days_until_expiry + ' days remaining' : Math.abs(exp.days_until_expiry) + ' days overdue'}`}
          </div>
        </div>
      </div>

      <FlagList flags={data.compliance_flags} />
      <JsonBlock data={data} id="lv4" />
    </SectionCard>
  )
}


// ─── Summary ──────────────────────────────────────────────────────────────────

function SummaryCard({ summary, processingMs }) {
  const riskColor = { LOW: 'var(--green)', MEDIUM: 'var(--warn)', HIGH: 'var(--accent2)', CRITICAL: 'var(--accent2)' }[summary.risk_level] || 'var(--muted)'
  return (
    <div className="summary-card fade-up">
      <div className="summary-header">
        <div>
          <div className="summary-label">OVERALL RESULT</div>
          <div className="summary-verdict" style={{
            color: summary.overall_verdict === 'PASS' ? 'var(--green)' : summary.overall_verdict === 'FAIL' ? 'var(--accent2)' : 'var(--warn)'
          }}>
            {summary.overall_verdict === 'PASS' ? '✅' : summary.overall_verdict === 'FAIL' ? '🚫' : '⚠️'} {summary.overall_verdict}
          </div>
        </div>
        <div className="summary-meta">
          <div className="risk-badge" style={{ background: `${riskColor}22`, color: riskColor, borderColor: `${riskColor}44` }}>
            RISK: {summary.risk_level}
          </div>
          <div className="proc-time">{processingMs}ms</div>
        </div>
      </div>

      <div className="summary-action">
        <strong>Notary Action:</strong> {summary.notary_action}
      </div>

      <div className="key-findings">
        {(summary.key_findings || []).map((f, i) => (
          <div key={i} className="finding-item">
            <span className="finding-bullet">▸</span>
            <span>{f}</span>
          </div>
        ))}
      </div>
    </div>
  )
}


// ─── Root ─────────────────────────────────────────────────────────────────────

export default function ResultsDashboard({ result, onReset }) {
  return (
    <div className="results-dashboard">
      <div className="results-top">
        <SummaryCard summary={result.summary} processingMs={result.processing_time_ms} />
        <button className="reset-btn" onClick={onReset}>← New Verification</button>
      </div>

      <div className="panels">
        <Level1Panel data={result.level1} />
        <Level2Panel data={result.level2} />
        <Level3Panel data={result.level3} />
        <Level4Panel data={result.level4} />
      </div>
    </div>
  )
}