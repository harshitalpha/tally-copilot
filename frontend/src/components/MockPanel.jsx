import { useEffect, useState } from 'react'
import { mockIncoming, getMockWALog } from '../api'

export default function MockPanel({ defaultPhone = '+91MOCK12345' }) {
  const [file, setFile] = useState(null)
  const [phone, setPhone] = useState(defaultPhone)
  const [result, setResult] = useState(null)
  const [log, setLog] = useState([])
  const [sending, setSending] = useState(false)

  useEffect(() => {
    const tick = () => getMockWALog().then(setLog).catch(() => {})
    tick()
    const id = setInterval(tick, 3000)
    return () => clearInterval(id)
  }, [])

  async function simulate() {
    if (!file) return
    setSending(true)
    setResult(null)
    try {
      const r = await mockIncoming(file, phone)
      setResult(r)
    } catch (e) {
      setResult({ error: e.message })
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="mt-8 rounded-lg border border-dashed border-slate-300 bg-slate-100 p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="inline-block rounded bg-slate-700 px-2 py-0.5 text-xs text-white">DEV</span>
        <h3 className="font-medium">Mock Panel — Simulate WhatsApp</h3>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <input type="file" onChange={e => setFile(e.target.files?.[0] || null)} className="text-sm" />
        <input
          type="text"
          value={phone}
          onChange={e => setPhone(e.target.value)}
          placeholder="+91XXXXXXXXXX"
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <button
          onClick={simulate}
          disabled={!file || sending}
          className="rounded bg-slate-900 px-3 py-1 text-sm text-white disabled:opacity-50"
        >
          {sending ? 'Sending…' : 'Simulate WhatsApp Invoice'}
        </button>
      </div>

      {result && (
        <pre className="mt-2 rounded bg-white p-2 text-xs">{JSON.stringify(result, null, 2)}</pre>
      )}

      <div className="mt-4">
        <h4 className="mb-1 text-sm font-medium text-slate-600">WA Send Log</h4>
        <div className="max-h-64 overflow-auto rounded border bg-white">
          {log.length === 0 && <div className="p-3 text-sm text-slate-400">No messages sent yet.</div>}
          {log.slice().reverse().map((m, i) => (
            <div key={i} className="border-b px-3 py-2 text-xs last:border-b-0">
              <div className="flex justify-between text-slate-500">
                <span>{m.to} · {m.type}</span>
                <span>{m.sent_at}</span>
              </div>
              <pre className="mt-1 whitespace-pre-wrap text-slate-800">{m.message_text}</pre>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
