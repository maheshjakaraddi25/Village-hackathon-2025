import { useRef, useState, useCallback } from 'react'
import './UploadPanel.css'

function DropZone({ label, icon, accept, file, onFile, hint, required }) {
  const inputRef = useRef()
  const [dragging, setDragging] = useState(false)
  const [preview, setPreview] = useState(null)

  const handleFile = (f) => {
    if (!f) return
    onFile(f)
    if (f.type.startsWith('image/')) {
      const reader = new FileReader()
      reader.onload = e => setPreview(e.target.result)
      reader.readAsDataURL(f)
    }
  }
  const clear = (e) => {
    e.stopPropagation()
    onFile(null)
    setPreview(null)
    inputRef.current.value = ''
  }

  return (
    <div
      className={`drop-zone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''} ${required ? 'required' : ''}`}
      onClick={() => inputRef.current.click()}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]) }}
    >
      <input ref={inputRef} type="file" accept={accept} style={{ display: 'none' }} onChange={e => handleFile(e.target.files[0])} />
      {preview ? (
        <div className="preview-wrap">
          <img src={preview} alt="preview" className="preview-img" />
          <div className="preview-meta">
            <div className="preview-name">{file.name}</div>
            <div className="preview-size">{(file.size / 1024).toFixed(0)} KB</div>
          </div>
          <button className="clear-btn" onClick={clear}>✕ Remove</button>
        </div>
      ) : (
        <div className="drop-content">
          <div className="drop-icon">{icon}</div>
          <div className="drop-label">{label}</div>
          {hint && <div className="drop-hint">{hint}</div>}
          <div className="drop-cta">Click or drag & drop</div>
          {required && <div className="drop-required">REQUIRED</div>}
        </div>
      )}
      {file && <div className="file-badge">✓ READY</div>}
    </div>
  )
}

function VoicePanel({ transcript, setTranscript }) {
  const [recording, setRecording] = useState(false)
  const [recObj, setRecObj] = useState(null)
  const [question, setQuestion] = useState(0)
  const QUESTIONS = [
    "Please state your full legal name, date of birth, and current residential address.",
    "What is the purpose of this notarization?",
    "Can you confirm the last four digits of your Social Security Number?",
    "Please spell your last name and confirm your current address.",
  ]
  const startRec = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { alert('Speech recognition requires Chrome or Edge. Type answer manually.'); return }
    const r = new SR()
    r.continuous = true; r.interimResults = true; r.lang = 'en-US'
    let final = transcript
    r.onresult = (e) => {
      let interim = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript + ' '
        else interim = e.results[i][0].transcript
      }
      setTranscript(final + interim)
    }
    r.start(); setRecObj(r); setRecording(true)
  }
  const stopRec = () => { recObj?.stop(); setRecording(false) }
  const speak = () => {
    const u = new SpeechSynthesisUtterance(QUESTIONS[question])
    u.rate = 0.9; window.speechSynthesis.speak(u)
  }

  return (
    <div className="voice-panel">
      <div className="voice-header">
        <span className="voice-title">Voice Identity Interview</span>
        <span className="voice-badge">OPTIONAL</span>
      </div>
      <div className="voice-question">
        <div className="vq-label">AI Notary asks:</div>
        <div className="vq-text">"{QUESTIONS[question]}"</div>
        <div className="vq-buttons">
          {QUESTIONS.map((_, i) => (
            <button key={i} className={`vq-btn ${question === i ? 'active' : ''}`} onClick={() => setQuestion(i)}>Q{i+1}</button>
          ))}
        </div>
      </div>
      <div className="voice-controls">
        <button className="voice-btn play" onClick={speak}>▶ Play Question</button>
        <button className={`voice-btn ${recording ? 'recording' : 'record'}`} onClick={recording ? stopRec : startRec}>
          {recording ? '⏹ Stop' : '⏺ Record Answer'}
        </button>
        {transcript && <button className="voice-btn clear" onClick={() => setTranscript('')}>✕ Clear</button>}
      </div>
      <textarea
        className="voice-transcript"
        value={transcript}
        onChange={e => setTranscript(e.target.value)}
        placeholder="Transcript appears here, or type manually..."
        rows={3}
      />
      <div className="voice-note">Voice data is sent to Claude for behavioral cross-reference with the ID document.</div>
    </div>
  )
}

export default function UploadPanel({ idFile, supportFile, onIdFile, onSupportFile, onAnalyze, onDemo, error }) {
  const [transcript, setTranscript] = useState('')
  const [showVoice, setShowVoice] = useState(false)

  return (
    <div className="upload-panel">
      <div className="upload-intro fade-up">
        <h2>Document Verification Pipeline</h2>
        <p>Upload a government-issued ID to run all four levels: authenticity check, field extraction, cross-document matching, and compliance flagging.</p>
      </div>

      <div className="upload-grid fade-up fade-up-delay-1">
        <DropZone label="GOVERNMENT-ISSUED ID" icon="🪪" accept="image/jpeg,image/png,image/webp"
          file={idFile} onFile={onIdFile} hint="Driver's license · Passport · State ID" required />
        <DropZone label="SUPPORTING DOCUMENT" icon="📄" accept="image/jpeg,image/png,image/webp"
          file={supportFile} onFile={onSupportFile} hint="Loan app · Deed · Utility bill — enables Level 3" />
      </div>

      <div className="voice-toggle-row fade-up fade-up-delay-1">
        <button className={`voice-toggle-btn ${showVoice ? 'active' : ''}`} onClick={() => setShowVoice(v => !v)}>
          🎙 {showVoice ? 'Hide' : 'Add'} Voice Interview
        </button>
        {transcript && <span className="transcript-indicator">✓ Transcript recorded ({transcript.length} chars)</span>}
      </div>

      {showVoice && <VoicePanel transcript={transcript} setTranscript={setTranscript} />}

      <div className="upload-actions fade-up fade-up-delay-2">
        <button className="btn-primary" onClick={onAnalyze} disabled={!idFile}>
          <span className="btn-icon">⚡</span> RUN FULL PIPELINE
        </button>
        <button className="btn-secondary" onClick={onDemo}>
          <span className="btn-icon">🧪</span> LOAD DEMO RESULT
        </button>
      </div>

      {error && (
        <div className="error-banner fade-up">
          <span>🚫</span>
          <div><strong>Verification failed</strong><p>{error}</p></div>
        </div>
      )}

      <div className="upload-notes fade-up fade-up-delay-3">
        <div className="note-item"><span>⚠️</span><span>Use synthetic or sample data only. Never upload real PII.</span></div>
        <div className="note-item"><span>🔒</span><span>Images processed by Claude Vision API and not stored on disk.</span></div>
        <div className="note-item"><span>📋</span><span>JPEG · PNG · WebP · Max 10MB per file</span></div>
      </div>
    </div>
  )
}
