import { useRef, useState } from 'react'
import './UploadPanel.css'

function DropZone({ label, icon, accept, file, onFile, hint }) {
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
    } else {
      setPreview(null)
    }
  }

  return (
    <div
      className={`drop-zone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
      onClick={() => inputRef.current.click()}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => {
        e.preventDefault()
        setDragging(false)
        handleFile(e.dataTransfer.files[0])
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        style={{ display: 'none' }}
        onChange={e => handleFile(e.target.files[0])}
      />

      {preview ? (
        <div className="preview-wrap">
          <img src={preview} alt="preview" className="preview-img" />
          <div className="preview-name">{file.name}</div>
          <div className="preview-size">{(file.size / 1024).toFixed(0)} KB</div>
        </div>
      ) : (
        <div className="drop-content">
          <div className="drop-icon">{icon}</div>
          <div className="drop-label">{label}</div>
          {hint && <div className="drop-hint">{hint}</div>}
          <div className="drop-cta">Click or drag & drop</div>
        </div>
      )}

      {file && <div className="file-badge">✓ READY</div>}
    </div>
  )
}

export default function UploadPanel({
  idFile, supportFile, onIdFile, onSupportFile,
  onAnalyze, onDemo, error
}) {
  return (
    <div className="upload-panel">
      <div className="upload-intro fade-up">
        <h2>Document Verification Pipeline</h2>
        <p>Upload an ID to run all four levels: authenticity check, field extraction, cross-document matching, and compliance flagging.</p>
      </div>

      <div className="upload-grid fade-up fade-up-delay-1">
        <DropZone
          label="GOVERNMENT-ISSUED ID"
          icon="🪪"
          accept="image/jpeg,image/png,image/webp"
          file={idFile}
          onFile={onIdFile}
          hint="Driver's license, passport, state ID"
        />
        <DropZone
          label="SUPPORTING DOCUMENT"
          icon="📄"
          accept="image/jpeg,image/png,image/webp"
          file={supportFile}
          onFile={onSupportFile}
          hint="Loan app, deed, utility bill (optional — enables Level 3)"
        />
      </div>

      <div className="upload-actions fade-up fade-up-delay-2">
        <button
          className="btn-primary"
          onClick={onAnalyze}
          disabled={!idFile}
        >
          <span className="btn-icon">⚡</span>
          RUN FULL PIPELINE
        </button>

        <button className="btn-secondary" onClick={onDemo}>
          <span className="btn-icon">🧪</span>
          LOAD DEMO RESULT
        </button>
      </div>

      {error && (
        <div className="error-banner fade-up">
          <span>🚫</span>
          <div>
            <strong>Verification failed</strong>
            <p>{error}</p>
          </div>
        </div>
      )}

      <div className="upload-notes fade-up fade-up-delay-3">
        <div className="note-item">
          <span className="note-icon">⚠️</span>
          <span>Use synthetic or sample data only. Never upload real PII.</span>
        </div>
        <div className="note-item">
          <span className="note-icon">🔒</span>
          <span>Images are sent to Claude Vision API and not stored.</span>
        </div>
        <div className="note-item">
          <span className="note-icon">📋</span>
          <span>Supports JPEG, PNG, WebP · Max 10MB per file.</span>
        </div>
      </div>
    </div>
  )
}