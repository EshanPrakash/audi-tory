import { useState } from 'react'
import './App.css'

// config
const API_URL = import.meta.env.VITE_API_URL
const MAX_TEXT_CHARS = 50_000

// available Polly neural voices
const VOICES = [
  { id: 'Matthew', label: 'Matthew (Masculine)' },
  { id: 'Joanna', label: 'Joanna (Feminine)' },
  { id: 'Ruth', label: 'Ruth (Feminine)' },
  { id: 'Stephen', label: 'Stephen (Masculine)' },
]

// converts a file object to a base64 string for the API
function toBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result.split(',')[1])
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

export default function App() {
  const [mode, setMode] = useState('pdf')
  const [pdf, setPdf] = useState(null)
  const [notes, setNotes] = useState('')
  const [style, setStyle] = useState('concepts')
  const [length, setLength] = useState('short')
  const [voice, setVoice] = useState('Matthew')
  const [loading, setLoading] = useState(false)
  const [downloadUrl, setDownloadUrl] = useState(null)
  const [error, setError] = useState(null)

  // clears results and errors when switching between pdf and text mode
  const handleModeSwitch = (newMode) => {
    setMode(newMode)
    setDownloadUrl(null)
    setError(null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setDownloadUrl(null)

    try {
      let body

      if (mode === 'pdf') {
        if (!pdf) throw new Error('Please select a PDF.')
        if (pdf.size > 5 * 1024 * 1024) throw new Error('PDF must be under 5MB.')
        const base64 = await toBase64(pdf)
        body = { pdf: base64, style, length, voice }
      } else {
        if (!notes.trim()) throw new Error('Please paste some notes.')
        if (notes.length > MAX_TEXT_CHARS) throw new Error(`Notes must be under ${MAX_TEXT_CHARS.toLocaleString()} characters.`)
        body = { notes, style, length, voice }
      }

      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Something went wrong.')
      setDownloadUrl(data.url)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // disable submit if loading or if the active input is empty
  const canSubmit = !loading && (mode === 'pdf' ? !!pdf : !!notes.trim())

  return (
    <div className="container">
      <h1>audi-tory</h1>
      <p className="subtitle">Upload your notes. Get audio.</p>

      <div className="mode-toggle">
        <button
          type="button"
          className={mode === 'pdf' ? 'active' : ''}
          onClick={() => handleModeSwitch('pdf')}
        >
          PDF Upload
        </button>
        <button
          type="button"
          className={mode === 'text' ? 'active' : ''}
          onClick={() => handleModeSwitch('text')}
        >
          Paste Text
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        {mode === 'pdf' ? (
          <div className="field">
            <label>PDF Notes</label>
            <input
              type="file"
              accept="application/pdf"
              onChange={(e) => { setPdf(e.target.files[0]); setDownloadUrl(null) }}
            />
          </div>
        ) : (
          <div className="field">
            <label>Notes <span className="char-count">{notes.length.toLocaleString()} / {MAX_TEXT_CHARS.toLocaleString()}</span></label>
            <textarea
              value={notes}
              onChange={(e) => { setNotes(e.target.value); setDownloadUrl(null) }}
              placeholder="Paste your notes here..."
              rows={8}
            />
          </div>
        )}

        <div className="field">
          <label>Style</label>
          <select value={style} onChange={(e) => setStyle(e.target.value)}>
            <option value="concepts">Core Concepts</option>
            <option value="podcast">Podcast</option>
            <option value="readback">Readback</option>
          </select>
        </div>

        <div className="field">
          <label>Length</label>
          <select value={length} onChange={(e) => setLength(e.target.value)}>
            <option value="short">Short (~200 words)</option>
            <option value="medium">Medium (~800 words)</option>
            <option value="long">Long (~1800 words)</option>
          </select>
        </div>

        <div className="field">
          <label>Voice</label>
          <select value={voice} onChange={(e) => setVoice(e.target.value)}>
            {VOICES.map((v) => (
              <option key={v.id} value={v.id}>{v.label}</option>
            ))}
          </select>
        </div>

        <button type="submit" disabled={!canSubmit}>
          {loading ? 'Generating audio...' : 'Generate Audio'}
        </button>
        {loading && <p className="loading-hint">This can take 20–30 seconds. Hang tight.</p>}
      </form>

      {error && <p className="error">{error}</p>}

      {downloadUrl && (
        <div className="result">
          <p>Your audio is ready.</p>
          <a href={downloadUrl} target="_blank" rel="noopener noreferrer">Download MP3</a>
        </div>
      )}
    </div>
  )
}
