import { useEffect, useRef, useState, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getMe, getActions, getActionStats, uploadDocument, exportCsvUrl } from '../api'
import StatusBadge from '../components/StatusBadge'
import MockPanel from '../components/MockPanel'

const STATUSES = ['', 'pending', 'processing', 'pending_review', 'pending_sync', 'synced', 'failed']

export default function Dashboard() {
  const nav = useNavigate()
  const [me, setMe] = useState(null)
  const [stats, setStats] = useState(null)
  const [actions, setActions] = useState([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [uploading, setUploading] = useState(false)
  const [err, setErr] = useState(null)
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef(null)

  const [filter, setFilter] = useState({ search: '', status: '', page: 1, page_size: 20 })

  const refresh = useCallback(() => {
    const params = {}
    if (filter.search) params.search = filter.search
    if (filter.status) params.status = filter.status
    params.page = filter.page
    params.page_size = filter.page_size
    getActions(params).then(r => {
      setActions(r.items || [])
      setTotal(r.total || 0)
      setTotalPages(r.total_pages || 1)
    }).catch(() => {})
  }, [filter])

  useEffect(() => {
    getMe().then(setMe).catch(() => {})
    getActionStats().then(setStats).catch(() => {})
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 4000)
    return () => clearInterval(id)
  }, [refresh])

  async function uploadFile(file) {
    if (!file) return
    setErr(null); setUploading(true)
    try { await uploadDocument(file); refresh() }
    catch (e) { setErr(e.message) }
    finally { setUploading(false) }
  }

  function logout() {
    localStorage.removeItem('token'); nav('/login')
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      {/* Header */}
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{me?.tally?.company_name || 'Tally Co-pilot'}</h1>
          <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
            <span className={`rounded-full px-2 py-0.5 ${me?.whatsapp?.is_verified ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200'}`}>
              WhatsApp {me?.whatsapp?.is_verified ? '✓' : '–'}
            </span>
            <span className={`rounded-full px-2 py-0.5 ${me?.tally?.connector_online ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
              Tally connector {me?.tally?.connector_online ? 'online' : 'offline'}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <Link to="/settings/infra" className="text-slate-500 hover:text-slate-900">Infrastructure</Link>
          <span className="text-slate-300">·</span>
          <Link to="/settings" className="text-slate-500 hover:text-slate-900">Settings</Link>
          <span className="text-slate-300">·</span>
          <button onClick={logout} className="text-slate-500 hover:text-slate-900">Sign out</button>
        </div>
      </header>

      {/* Stats cards */}
      {stats && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="This month" value={stats.this_month.total} sub="invoices" />
          <StatCard label="Synced" value={stats.this_month.synced} sub={`${stats.this_month.success_rate}% success`} color="emerald" />
          <StatCard label="Failed" value={stats.this_month.failed} sub="this month" color={stats.this_month.failed > 0 ? 'rose' : undefined} />
          <StatCard label="Amount processed" value={`₹${(stats.this_month.total_amount_inr/1000).toFixed(1)}K`} sub="this month" />
        </div>
      )}

      {/* Upload zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); uploadFile(e.dataTransfer.files?.[0]) }}
        className={`mb-4 cursor-pointer rounded-lg border-2 border-dashed p-6 text-center transition
          ${dragging ? 'border-slate-900 bg-slate-100' : 'border-slate-300 bg-white'}`}
        onClick={() => fileRef.current?.click()}
      >
        <input ref={fileRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.heic" className="hidden"
          onChange={e => uploadFile(e.target.files?.[0])} />
        <div className="text-sm text-slate-600">
          {uploading ? 'Uploading…' : 'Drop invoice here or click to upload — PDF, JPG, PNG, HEIC'}
        </div>
      </div>

      {err && <div className="mb-3 rounded bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}

      {/* Filters */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          type="text"
          placeholder="Search supplier…"
          value={filter.search}
          onChange={e => setFilter(f => ({ ...f, search: e.target.value, page: 1 }))}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <select
          value={filter.status}
          onChange={e => setFilter(f => ({ ...f, status: e.target.value, page: 1 }))}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        >
          {STATUSES.map(s => <option key={s} value={s}>{s || 'All statuses'}</option>)}
        </select>
        <div className="ml-auto flex items-center gap-2">
          <a
            href={exportCsvUrl(filter.status ? { status: filter.status } : {})}
            download
            className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
          >
            Export CSV
          </a>
          <span className="text-xs text-slate-400">{total} invoices</span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-lg border bg-white">
        {actions.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-400">No invoices yet.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Supplier</th>
                <th className="px-4 py-2">Invoice #</th>
                <th className="px-4 py-2 text-right">Amount</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Source</th>
                <th className="px-4 py-2">Date</th>
              </tr>
            </thead>
            <tbody>
              {actions.map(a => {
                const inv = a.data?.extracted_invoice || {}
                return (
                  <tr key={a.id} onClick={() => nav(`/actions/${a.id}`)}
                    className="cursor-pointer border-t hover:bg-slate-50">
                    <td className="px-4 py-2">{inv.supplier_name || '—'}</td>
                    <td className="px-4 py-2 text-slate-500">{inv.invoice_number || '—'}</td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {inv.total_amount ? `₹${Number(inv.total_amount).toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '—'}
                    </td>
                    <td className="px-4 py-2"><StatusBadge status={a.status} /></td>
                    <td className="px-4 py-2 text-xs text-slate-500">{a.data?.source || '—'}</td>
                    <td className="px-4 py-2 text-xs text-slate-500">{a.created_at?.slice(0, 10)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-3 flex items-center justify-center gap-2 text-sm">
          <button disabled={filter.page <= 1}
            onClick={() => setFilter(f => ({ ...f, page: f.page - 1 }))}
            className="rounded border px-3 py-1 disabled:opacity-40">← Prev</button>
          <span className="text-slate-500">Page {filter.page} of {totalPages}</span>
          <button disabled={filter.page >= totalPages}
            onClick={() => setFilter(f => ({ ...f, page: f.page + 1 }))}
            className="rounded border px-3 py-1 disabled:opacity-40">Next →</button>
        </div>
      )}

      {import.meta.env.DEV && (
        <MockPanel defaultPhone={me?.whatsapp?.phone_number || '+91MOCK12345'} />
      )}
    </div>
  )
}

function StatCard({ label, value, sub, color }) {
  const colors = {
    emerald: 'text-emerald-700',
    rose:    'text-rose-700',
  }
  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`text-2xl font-bold ${colors[color] || 'text-slate-900'}`}>{value}</div>
      <div className="text-xs text-slate-400">{sub}</div>
    </div>
  )
}
