import './LoadingState.css'

const STEPS = [
  { label: 'LV1', name: 'Document Authenticity Check', desc: 'Font analysis · Field formats · Security features · Layout validation' },
  { label: 'LV2', name: 'Field Extraction & Structuring', desc: 'OCR · Name · DOB · Address · ID number · Expiration · Class' },
  { label: 'LV3', name: 'Cross-Document Identity Match', desc: 'Name comparison · Address validation · DOB cross-check' },
  { label: 'LV4', name: 'Compliance Flagging', desc: 'Expiration · In-state rules · NIST IAL2 · MISMO standards' },
]

export default function LoadingState() {
  return (
    <div className="loading-wrap fade-up">
      <div className="scanner-visual">
        <div className="scan-frame">
          <div className="scan-corner tl" />
          <div className="scan-corner tr" />
          <div className="scan-corner bl" />
          <div className="scan-corner br" />
          <div className="scan-icon">🪪</div>
          <div className="scan-line" />
        </div>
        <div className="scan-label">ANALYZING DOCUMENT</div>
      </div>

      <div className="loading-steps">
        {STEPS.map((s, i) => (
          <div key={i} className="loading-step" style={{ animationDelay: `${i * 0.15}s` }}>
            <div className="step-badge" style={{
              background: ['var(--green-dim)','var(--warn-dim)','var(--accent-dim)','var(--accent2-dim)'][i],
              color: ['var(--green)','var(--warn)','var(--accent)','var(--accent2)'][i],
              borderColor: ['rgba(0,230,118,0.25)','rgba(255,180,0,0.25)','rgba(0,229,255,0.25)','rgba(255,61,113,0.25)'][i],
            }}>
              {s.label}
            </div>
            <div>
              <div className="step-name">{s.name}</div>
              <div className="step-desc">{s.desc}</div>
            </div>
            <div className="step-spinner" style={{ animationDelay: `${i * 0.4}s` }} />
          </div>
        ))}
      </div>

      <div className="loading-footer">
        <span>Powered by Claude claude-sonnet-4-20250514 Vision</span>
        <span>·</span>
        <span>Full pipeline · ~5–15s</span>
      </div>
    </div>
  )
}