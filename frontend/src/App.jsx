import { useState, useCallback } from 'react'
import UploadPanel from './components/UploadPanel.jsx'
import ResultsDashboard from './components/ResultsDashboard.jsx'
import LoadingState from './components/LoadingState.jsx'
import HistoryPanel from './components/HistoryPanel.jsx'
import './App.css'

export default function App() {
  const [idFile, setIdFile] = useState(null)
  const [supportFile, setSupportFile] = useState(null)
  const [status, setStatus] = useState('idle')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('verify')

  const handleAnalyze = useCallback(async () => {
    if (!idFile) return
    setStatus('loading')
    setResult(null)
    setError(null)
    try {
      const form = new FormData()
      form.append('id_doc', idFile)
      if (supportFile) form.append('support_doc', supportFile)
      const res = await fetch('/verify', { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setResult(data)
      setStatus('done')
    } catch (e) {
      setError(e.message)
      setStatus('error')
    }
  }, [idFile, supportFile])

  const handleDemo = useCallback(async () => {
    setStatus('loading')
    setResult(null)
    setError(null)
    try {
      const res = await fetch('/synthetic-test', { method: 'POST' })
      const data = await res.json()
      setResult(data)
      setStatus('done')
    } catch (e) {
      setError(e.message)
      setStatus('error')
    }
  }, [])

  const handleReset = () => {
    setStatus('idle')
    setResult(null)
    setError(null)
    setIdFile(null)
    setSupportFile(null)
  }

  return (
    <div className="app-shell">
      <header className="app-header fade-up">
        <div className="header-left">
          <div className="logo-mark">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="2"/><line x1="12" y1="2" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22"/>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
              <line x1="2" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="22" y2="12"/>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
          </div>
          <div>
            <h1 className="app-title">ID Verify <span>AI</span></h1>
            <p className="app-sub">VillageHacks 2026 · Notary Everyday</p>
          </div>
        </div>
        <div className="header-right">
          <div className="level-chips">
            {['LV1 AUTHENTIC', 'LV2 EXTRACT', 'LV3 CROSS-DOC', 'LV4 COMPLY'].map((l, i) => (
              <span key={i} className={`chip chip-${i + 1}`}>{l}</span>
            ))}
          </div>
          <div className="nav-tabs">
            <button className={`nav-tab ${activeTab === 'verify' ? 'active' : ''}`} onClick={() => setActiveTab('verify')}>Verify</button>
            <button className={`nav-tab ${activeTab === 'history' ? 'active' : ''}`} onClick={() => setActiveTab('history')}>History</button>
          </div>
        </div>
      </header>

      <main className="app-main">
        {activeTab === 'history' ? (
          <HistoryPanel onLoadResult={(r) => { setResult(r); setStatus('done'); setActiveTab('verify'); }} />
        ) : status === 'idle' || status === 'error' ? (
          <UploadPanel
            idFile={idFile} supportFile={supportFile}
            onIdFile={setIdFile} onSupportFile={setSupportFile}
            onAnalyze={handleAnalyze} onDemo={handleDemo} error={error}
          />
        ) : status === 'loading' ? (
          <LoadingState />
        ) : (
          <ResultsDashboard result={result} onReset={handleReset} />
        )}
      </main>
    </div>
  )
}
