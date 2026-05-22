import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getMe, getActions, uploadDocument } from '../api'
import StatusBadge from '../components/StatusBadge'
import MockPanel from '../components/MockPanel'

export default function Dashboard() {
  const nav = useNavigate()
  const [me, setMe] = useState(null)
  const [actions, setActions] = useState([])
  const [uploading, setUploading] = useState(false)
  const [err, setErr] = useState(null)
  const fileRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    getMe().then(setMe).catch(() => {})
    refresh()
    const id = setInterval(refresh, 3000)
    return () => clearInterval(id)
  }, [])

  function refresh() {
    getActions().then(r => setActions(r.items || [])).catch(() => {})
  }

  async function uploadFile(file) {
    if (!file) return
    setErr(null); setUploading(true)
    try {
      await uploadDocument(file)
      refresh()
    } catch (e) { setErr(e.message) }
    finally { setUploading(false) }
  }

  function logout() {
    localStorage.removeItem('token')
    nav('/login')
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{me?.tally?.company_name || 'Tally Co-pilot'}</h1>
          <div className="mt-1 flex gap-2 text-xs text-slate-500">
            <span className={`rounded-full px-2 py-0.5 ${me?.whatsapp?.is_verified ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200'}`}>
              WhatsApp {me?.whatsapp?.is_verified ? '✓' : '–'}
            </span>
            <span className={`rounded-full px-2 py-0.5 ${me?.tally?.connector_online ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
              Tally connector {me?.tally?.connector_online ? 'online' : 'offline'}
            </span>
          </div>
        </div>
        <button onClick={logout} className="text-sm text-slate-500 hover:text-slate-900">Sign out</button>
      </header>

      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => {
          e.preventDefault(); setDragging(false)
          uploadFile(e.dataTransfer.files?.[0])
        }}
        className={`mb-6 cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition
          ${dragging ? 'border-slate-900 bg-slate-100' : 'border-slate-300 bg-white'}`}
        onClick={() => fileRef.current?.click()}
      >
        <input ref={fileRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.heic" className="hidden"
          onChange={e => uploadFile(e.target.files?.[0])} />
        <div className="text-sm text-slate-600">
          {uploading ? 'Uploading…' : 'Drop an invoice here or click to upload (PDF / JPG / PNG)'}
        </div>
      </div>

      {err && <div className="mb-4 rounded bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}

      <h2 className="mb-2 text-lg font-medium">Recent invoices</h2>
      <div className="overflow-hidden rounded-lg border bg-white">
        {actions.length === 0 ? (
          <div className="p-6 text-center text-sm text-slate-400">No invoices yet.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Supplier</th>
                <th className="px-4 py-2">Invoice #</th>
                <th className="px-4 py-2 text-right">Amount</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Source</th>
                <th className="px-4 py-2">Time</th>
              </tr>
            </thead>
            <tbody>
              {actions.map(a => {
                const inv = a.data?.extracted_invoice || {}
                return (
                  <tr key={a.id}
                    onClick={() => nav(`/actions/${a.id}`)}
                    className="cursor-pointer border-t hover:bg-slate-50">
                    <td className="px-4 py-2">{inv.supplier_name || '—'}</td>
                    <td className="px-4 py-2 text-slate-500">{inv.invoice_number || '—'}</td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {inv.total_amount ? `₹${Number(inv.total_amount).toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '—'}
                    </td>
                    <td className="px-4 py-2"><StatusBadge status={a.status} /></td>
                    <td className="px-4 py-2 text-xs text-slate-500">{a.data?.source || '—'}</td>
                    <td className="px-4 py-2 text-xs text-slate-500">{a.created_at?.slice(0, 19).replace('T', ' ')}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {import.meta.env.DEV && (
        <MockPanel defaultPhone={me?.whatsapp?.phone_number || '+91MOCK12345'} />
      )}
    </div>
  )
}
