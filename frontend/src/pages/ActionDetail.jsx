import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getAction, documentFileUrl } from '../api'
import StatusBadge from '../components/StatusBadge'

export default function ActionDetail() {
  const { id } = useParams()
  const [action, setAction] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let cancel = false
    function tick() {
      getAction(id).then(a => { if (!cancel) setAction(a) }).catch(e => setErr(e.message))
    }
    tick()
    const t = setInterval(tick, 3000)
    return () => { cancel = true; clearInterval(t) }
  }, [id])

  if (err) return <div className="p-8 text-rose-700">{err}</div>
  if (!action) return <div className="p-8 text-slate-500">Loading…</div>

  const d = action.data || {}
  const inv = d.extracted_invoice || {}
  const docId = d.document_id
  const ext = (inv && inv.file_type) || null
  const url = docId ? documentFileUrl(docId) : null
  const tokenQS = `?t=${encodeURIComponent(localStorage.getItem('token') || '')}`

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <div className="mb-4">
        <Link to="/dashboard" className="text-sm text-slate-500 hover:text-slate-900">← Back</Link>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-lg border bg-white">
          {url ? (
            <DocViewer url={url} />
          ) : (
            <div className="p-6 text-sm text-slate-400">No document</div>
          )}
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <StatusBadge status={action.status} large />
            <div className="text-xs text-slate-500">
              Source: {d.source || '—'}{d.sender_phone ? ` · ${d.sender_phone}` : ''}
            </div>
          </div>

          {action.status === 'synced' && (
            <div className="rounded bg-emerald-50 p-3 text-sm text-emerald-800">
              ✅ Posted to Tally · Voucher <span className="font-mono">{d.tally_voucher_id || '—'}</span>
            </div>
          )}
          {action.status === 'failed' && (
            <div className="rounded bg-rose-50 p-3 text-sm text-rose-700">
              ❌ {d.tally_error || 'Unknown error'}
            </div>
          )}

          {d.validation_errors?.length > 0 && (
            <div className="rounded bg-rose-50 p-3 text-sm">
              <div className="font-medium text-rose-800">Validation errors</div>
              <ul className="list-inside list-disc text-rose-700">{d.validation_errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
            </div>
          )}
          {d.validation_warnings?.length > 0 && (
            <div className="rounded bg-amber-50 p-3 text-sm">
              <div className="font-medium text-amber-800">Warnings</div>
              <ul className="list-inside list-disc text-amber-700">{d.validation_warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
            </div>
          )}

          <div className="rounded-lg border bg-white p-4">
            <h3 className="mb-2 text-sm font-medium text-slate-600">Extracted invoice</h3>
            <Field label="Supplier" value={inv.supplier_name} />
            <Field label="Supplier GSTIN" value={inv.supplier_gstin} mono />
            <Field label="Invoice #" value={inv.invoice_number} />
            <Field label="Date" value={inv.invoice_date} />
            <Field label="Place of supply" value={inv.place_of_supply} />
            <Field label="Reverse charge" value={inv.reverse_charge ? 'Yes' : 'No'} />
            <div className="mt-3 border-t pt-3">
              <Field label="Taxable amount" value={fmtAmt(inv.total_taxable_amount)} />
              <Field label="CGST" value={fmtAmt(inv.total_cgst)} />
              <Field label="SGST" value={fmtAmt(inv.total_sgst)} />
              <Field label="IGST" value={fmtAmt(inv.total_igst)} />
              <Field label="Total" value={fmtAmt(inv.total_amount)} bold />
            </div>

            {inv.line_items?.length > 0 && (
              <div className="mt-4">
                <h4 className="mb-1 text-xs uppercase tracking-wider text-slate-500">Line items</h4>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-slate-500">
                      <th className="py-1">Description</th>
                      <th className="py-1 text-right">Qty</th>
                      <th className="py-1 text-right">Rate</th>
                      <th className="py-1 text-right">Taxable</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inv.line_items.map((li, i) => (
                      <tr key={i} className="border-t">
                        <td className="py-1">{li.description}</td>
                        <td className="py-1 text-right">{li.quantity}</td>
                        <td className="py-1 text-right">{fmtAmt(li.rate)}</td>
                        <td className="py-1 text-right">{fmtAmt(li.taxable_amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function Field({ label, value, mono, bold }) {
  return (
    <div className="flex justify-between py-1 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className={`${mono ? 'font-mono' : ''} ${bold ? 'font-semibold' : ''} text-slate-900`}>{value || '—'}</span>
    </div>
  )
}

function fmtAmt(n) {
  if (n === null || n === undefined || n === '') return null
  const num = Number(n)
  if (Number.isNaN(num)) return null
  return `₹${num.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function DocViewer({ url }) {
  // Document file route requires Authorization; fetch as blob and create object URL.
  const [blobUrl, setBlobUrl] = useState(null)
  const [isImage, setIsImage] = useState(false)

  useEffect(() => {
    let mounted = true
    let created = null
    fetch(url, { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } })
      .then(async r => {
        const blob = await r.blob()
        if (!mounted) return
        created = URL.createObjectURL(blob)
        setBlobUrl(created)
        setIsImage(blob.type.startsWith('image/'))
      })
      .catch(() => {})
    return () => {
      mounted = false
      if (created) URL.revokeObjectURL(created)
    }
  }, [url])

  if (!blobUrl) return <div className="p-6 text-sm text-slate-400">Loading document…</div>
  if (isImage) return <img src={blobUrl} alt="invoice" className="max-h-[80vh] w-full object-contain" />
  return <iframe src={blobUrl} title="invoice" className="h-[80vh] w-full" />
}
