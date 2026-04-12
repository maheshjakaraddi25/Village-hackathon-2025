import { useState } from 'react'
import './ResultsDashboard.css'

// ─── Primitives ───────────────────────────────────────────────────────────────

function VerdictBanner({ verdict, message }) {
  const map = { PASS: { cls: 'pass', icon: '✅' }, FAIL: { cls: 'fail', icon: '🚫' }, WARN: { cls: 'warn', icon: '⚠️' }, PROCEED: { cls: 'pass', icon: '✅' }, HOLD: { cls: 'warn', icon: '⚠️' }, REJECT: { cls: 'fail', icon: '🚫' } }
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

function JsonBlock({ data }) {
  const [copied, setCopied] = useState(false)
  const [open, setOpen] = useState(false)
  const str = JSON.stringify(data, null, 2)
  const copy = () => { navigator.clipboard.writeText(str).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500) }) }
  return (
    <div className="json-wrap">
      <button className="json-toggle" onClick={() => setOpen(o => !o)}>{open ? '▲ HIDE JSON' : '▼ SHOW JSON'}</button>
      {open && <>
        <button className="copy-btn" onClick={copy}>{copied ? '✓ COPIED' : 'COPY'}</button>
        <pre className="json-block">{str}</pre>
      </>}
    </div>
  )
}

function SectionCard({ level, levelColor, title, rightLabel, rightColor, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="section-card">
      <div className="section-header" onClick={() => setOpen(o => !o)}>
        <div className="section-left">
          <div className="section-badge" style={{ background: `${levelColor}1a`, color: levelColor, borderColor: `${levelColor}33` }}>{level}</div>
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

// ─── Level Panels ─────────────────────────────────────────────────────────────

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
          <span className="suspicious-label">🔎 Suspicious:</span>
          {data.suspicious_elements.map((s, i) => <span key={i} className="suspicious-tag">{s}</span>)}
        </div>
      )}
      <JsonBlock data={data} />
    </SectionCard>
  )
}

function Level2Panel({ data }) {
  const conf = Math.round((data.extraction_confidence || 0) * 100)
  const ef = data.extracted_fields || {}
  const fieldLabels = { first_name: 'First Name', last_name: 'Last Name', dob: 'Date of Birth', id_number: 'ID Number', expiration: 'Expiration', address: 'Address', license_class: 'Class', issuing_state: 'State', issuing_country: 'Country', gender: 'Gender', height: 'Height', eye_color: 'Eye Color' }
  return (
    <SectionCard level="LV2" levelColor="#ffb400" title="Field Extraction & Structuring" rightLabel={`${conf}% CONFIDENCE`} rightColor={conf >= 70 ? 'var(--green)' : 'var(--warn)'}>
      <div className="fields-grid">
        {Object.entries(ef).map(([k, v]) => (
          <div key={k} className={`field-item ${!v ? 'field-empty' : ''}`}>
            <div className="field-key">{fieldLabels[k] || k.replace(/_/g,' ').toUpperCase()}</div>
            <div className="field-val">{v || <span className="field-null">not detected</span>}</div>
          </div>
        ))}
      </div>
      <div className="conf-section">
        <div className="conf-section-title">Field Confidence</div>
        {Object.entries(data.field_confidences || {}).map(([k, v]) => (
          <ConfidenceBar key={k} label={fieldLabels[k] || k} value={v} />
        ))}
      </div>
      {data.ocr_issues?.length > 0 && (
        <div className="ocr-issues">⚠ OCR Issues: {data.ocr_issues.join(' · ')}</div>
      )}
      <JsonBlock data={ef} />
    </SectionCard>
  )
}

function Level3Panel({ data }) {
  if (!data.cross_doc_available) {
    return (
      <SectionCard level="LV3" levelColor="#00e5ff" title="Cross-Document Identity Match" rightLabel="NO SECOND DOC" rightColor="var(--muted)">
        <div className="no-doc-msg">Upload a second supporting document (loan app, deed, utility bill) to enable cross-document analysis and unlock Level 3.</div>
      </SectionCard>
    )
  }
  const score = Math.round((data.overall_match_score || 0) * 100)
  const scoreColor = score >= 70 ? 'var(--green)' : score >= 40 ? 'var(--warn)' : 'var(--accent2)'
  const consistencyVerdict = data.identity_consistency === 'CONSISTENT' ? 'PASS' : data.identity_consistency === 'INCONSISTENT' ? 'FAIL' : 'WARN'
  return (
    <SectionCard level="LV3" levelColor="#00e5ff" title="Cross-Document Identity Match" rightLabel={`${score}% MATCH`} rightColor={scoreColor}>
      <VerdictBanner verdict={consistencyVerdict} message={`Identity Consistency: ${data.identity_consistency}`} />
      <div className="comparison-table">
        <div className="comp-header">
          <span>FIELD</span><span>ID VALUE</span><span>DOCUMENT VALUE</span><span>CONF</span><span>STATUS</span>
        </div>
        {(data.comparisons || []).map((c, i) => {
          const flagColor = c.flag === 'MATCH' ? 'var(--green)' : c.flag === 'MISMATCH' ? 'var(--accent2)' : c.flag === 'UNAVAILABLE' ? 'var(--muted)' : 'var(--warn)'
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
      <JsonBlock data={data} />
    </SectionCard>
  )
}

function Level4Panel({ data }) {
  const exp = data.expiration_status || {}
  const expColor = exp.status === 'VALID' ? 'var(--green)' : exp.status === 'EXPIRED' ? 'var(--accent2)' : exp.status === 'EXPIRING_SOON' ? 'var(--warn)' : 'var(--muted)'
  const expIcon = exp.status === 'VALID' ? '✅' : exp.status === 'EXPIRED' ? '🚫' : '⚠️'
  const recColor = data.overall_recommendation === 'PROCEED' ? 'var(--green)' : data.overall_recommendation === 'REJECT' ? 'var(--accent2)' : 'var(--warn)'
  return (
    <SectionCard level="LV4" levelColor="#ff3d71" title="Expiration & Compliance" rightLabel={data.overall_recommendation} rightColor={recColor}>
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
      <JsonBlock data={data} />
    </SectionCard>
  )
}

// ─── Summary ──────────────────────────────────────────────────────────────────

function SummaryCard({ summary, processingMs, resultId }) {
  const riskColor = { LOW: 'var(--green)', MEDIUM: 'var(--warn)', HIGH: 'var(--accent2)', CRITICAL: 'var(--accent2)' }[summary.risk_level] || 'var(--muted)'
  const verdictColor = summary.overall_verdict === 'PASS' ? 'var(--green)' : summary.overall_verdict === 'FAIL' ? 'var(--accent2)' : 'var(--warn)'
  const verdictIcon = summary.overall_verdict === 'PASS' ? '✅' : summary.overall_verdict === 'FAIL' ? '🚫' : '⚠️'

  return (
    <div className="summary-card fade-up">
      <div className="summary-header">
        <div>
          {resultId && <div className="result-id-label">Verification #{resultId}</div>}
          <div className="summary-label">OVERALL RESULT</div>
          <div className="summary-verdict" style={{ color: verdictColor }}>
            {verdictIcon} {summary.overall_verdict}
          </div>
        </div>
        <div className="summary-meta">
          <div className="risk-badge" style={{ background: `${riskColor}1a`, color: riskColor, borderColor: `${riskColor}33` }}>
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

// ─── Export helpers ───────────────────────────────────────────────────────────

function ExportBar({ result }) {
  const exportJSON = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `verification-${result.id || 'result'}-${Date.now()}.json`
    a.click()
  }
  const exportText = () => {
    const s = result.summary || {}
    const f = result.level2?.extracted_fields || {}
    const lines = [
      `ID VERIFICATION REPORT`,
      `Generated: ${new Date().toLocaleString()}`,
      `Verification ID: ${result.id || 'N/A'}`,
      `─────────────────────────────`,
      `OVERALL: ${s.overall_verdict} · RISK: ${s.risk_level}`,
      `NOTARY ACTION: ${s.notary_action}`,
      ``,
      `SUBJECT: ${f.first_name || ''} ${f.last_name || ''}`.trim(),
      `DOB: ${f.dob || 'N/A'}`,
      `ID#: ${f.id_number || 'N/A'}`,
      `STATE: ${f.issuing_state || 'N/A'}`,
      `EXPIRES: ${f.expiration || 'N/A'}`,
      `ADDRESS: ${f.address || 'N/A'}`,
      ``,
      `KEY FINDINGS:`,
      ...(s.key_findings || []).map(f => `  • ${f}`),
      ``,
      `RECOMMENDATION: ${result.level4?.overall_recommendation || 'N/A'}`,
      `${result.level4?.recommendation_detail || ''}`,
      ``,
      `Processing time: ${result.processing_time_ms}ms`,
    ]
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `verification-${result.id || 'result'}-${Date.now()}.txt`
    a.click()
  }

  return (
    <div className="export-bar">
      <span className="export-label">EXPORT:</span>
      <button className="export-btn" onClick={exportJSON}>⬇ JSON</button>
      <button className="export-btn" onClick={exportText}>⬇ Text Report</button>
      <button className="export-btn" onClick={() => window.print()}>🖨 Print</button>
    </div>
  )
}

// ─── Root ─────────────────────────────────────────────────────────────────────

export default function ResultsDashboard({ result, onReset }) {
  return (
    <div className="results-dashboard">
      <div className="results-top">
        <SummaryCard summary={result.summary} processingMs={result.processing_time_ms} resultId={result.id} />
        <div className="results-actions">
          <ExportBar result={result} />
          <button className="reset-btn" onClick={onReset}>← New Verification</button>
        </div>
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
