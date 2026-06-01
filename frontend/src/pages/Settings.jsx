import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  getSettings, saveTallySettings, saveReviewMode,
  connectWASetting, verifyWASetting,
} from '../api'

export default function Settings() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [saved, setSaved] = useState(null)

  const refresh = () => getSettings().then(setData).catch(e => setErr(e.message))
  useEffect(() => { refresh() }, [])

  if (err) return <Wrap><div className="rounded bg-rose-50 p-3 text-sm text-rose-700">{err}</div></Wrap>
  if (!data) return <Wrap><div className="text-sm text-slate-500">Loading…</div></Wrap>

  return (
    <Wrap>
      <TallySection data={data} onSaved={() => { refresh(); setSaved('tally') }} />
      <ReviewSection data={data} onSaved={() => { refresh(); setSaved('review') }} />
      <WhatsAppSection data={data} onSaved={() => { refresh(); setSaved('wa') }} />
      {saved && (
        <div className="fixed bottom-4 right-4 rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white shadow">
          Settings saved ✓
        </div>
      )}
    </Wrap>
  )
}

function Wrap({ children }) {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <div className="mb-6">
        <Link to="/dashboard" className="text-sm text-slate-500 hover:text-slate-900">← Back</Link>
        <h1 className="mt-1 text-2xl font-semibold">Settings</h1>
      </div>
      <div className="space-y-6">{children}</div>
    </div>
  )
}

function TallySection({ data, onSaved }) {
  const t = data.tally || {}
  const [form, setForm] = useState({
    purchase_ledger:    t.purchase_ledger    ?? 'Purchases',
    cgst_ledger_format: t.cgst_ledger_format ?? 'CGST @ {rate}%',
    sgst_ledger_format: t.sgst_ledger_format ?? 'SGST @ {rate}%',
    igst_ledger_format: t.igst_ledger_format ?? 'IGST @ {rate}%',
    auto_create_ledgers: t.auto_create_ledgers ?? true,
  })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  async function save(e) {
    e.preventDefault(); setErr(null); setBusy(true)
    try { await saveTallySettings(form); onSaved() }
    catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  return (
    <Card title="Tally ledger mappings"
      subtitle={data.tally?.company_name ? `Connected to ${data.tally.company_name}` : 'Not connected'}>
      <form onSubmit={save} className="space-y-3">
        {['purchase_ledger','cgst_ledger_format','sgst_ledger_format','igst_ledger_format'].map(k => (
          <div key={k}>
            <label className="mb-1 block text-sm font-medium">{k}</label>
            <input value={form[k]} onChange={set(k)} className="w-full rounded border border-slate-300 px-3 py-2 text-sm" />
          </div>
        ))}
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.auto_create_ledgers}
            onChange={e => setForm(f => ({ ...f, auto_create_ledgers: e.target.checked }))} />
          Auto-create missing ledgers in Tally
        </label>
        {err && <div className="rounded bg-rose-50 p-2 text-sm text-rose-700">{err}</div>}
        <button disabled={busy} className="rounded bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50">
          {busy ? 'Saving…' : 'Save Tally settings'}
        </button>
      </form>
    </Card>
  )
}

function ReviewSection({ data, onSaved }) {
  const [enabled, setEnabled] = useState(data.require_review_before_tally ?? false)
  const [busy, setBusy] = useState(false)

  async function toggle() {
    const next = !enabled; setBusy(true)
    try { await saveReviewMode(next); setEnabled(next); onSaved() }
    catch { /* ignore */ }
    finally { setBusy(false) }
  }

  return (
    <Card title="Manual review mode"
      subtitle="When enabled, invoices wait for your approval before posting to Tally.">
      <div className="flex items-center justify-between">
        <div className="text-sm text-slate-600">
          {enabled
            ? 'On — invoices go to pending review before Tally'
            : 'Off — invoices post to Tally automatically after extraction'}
        </div>
        <button onClick={toggle} disabled={busy}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${enabled ? 'bg-emerald-500' : 'bg-slate-300'}`}>
          <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition ${enabled ? 'translate-x-6' : 'translate-x-1'}`} />
        </button>
      </div>
    </Card>
  )
}

function WhatsAppSection({ data, onSaved }) {
  const wa = data.whatsapp
  const [phone, setPhone] = useState(wa?.phone_number || '+91')
  const [otp, setOtp] = useState('')
  const [devOtp, setDevOtp] = useState(null)
  const [step, setStep] = useState(wa?.is_verified ? 'verified' : 'enter')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  async function connect() {
    setErr(null); setBusy(true)
    try {
      const r = await connectWASetting(phone)
      setDevOtp(r.dev_otp || null)
      setStep('otp')
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  async function verify() {
    setErr(null); setBusy(true)
    try { await verifyWASetting(otp); setStep('verified'); onSaved() }
    catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  return (
    <Card title="WhatsApp number"
      subtitle="Send invoices from this number for automatic processing. Optional.">
      {step === 'verified' && (
        <div className="flex items-center justify-between">
          <div className="text-sm">
            <span className="text-emerald-600">✓ Verified:</span>{' '}
            <span className="font-mono">{wa?.phone_number}</span>
          </div>
          <button onClick={() => setStep('enter')} className="text-xs text-slate-500 hover:text-slate-900 underline">Change</button>
        </div>
      )}
      {step === 'enter' && (
        <div className="space-y-2">
          <input value={phone} onChange={e => setPhone(e.target.value)} placeholder="+91XXXXXXXXXX"
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm font-mono" />
          {err && <div className="rounded bg-rose-50 p-2 text-sm text-rose-700">{err}</div>}
          <button onClick={connect} disabled={busy} className="rounded bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50">
            {busy ? 'Sending…' : wa?.is_verified ? 'Update number' : 'Send OTP'}
          </button>
        </div>
      )}
      {step === 'otp' && (
        <div className="space-y-2">
          {devOtp && (
            <div className="rounded bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              DEV OTP: <span className="font-mono text-base font-bold">{devOtp}</span>
            </div>
          )}
          <input value={otp} onChange={e => setOtp(e.target.value)} placeholder="6-digit OTP"
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm" />
          {err && <div className="rounded bg-rose-50 p-2 text-sm text-rose-700">{err}</div>}
          <button onClick={verify} disabled={busy || !otp} className="rounded bg-emerald-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">
            {busy ? 'Verifying…' : 'Verify'}
          </button>
        </div>
      )}
    </Card>
  )
}

function Card({ title, subtitle, children }) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <h3 className="font-medium text-slate-900">{title}</h3>
      {subtitle && <p className="mb-3 text-xs text-slate-500">{subtitle}</p>}
      {children}
    </div>
  )
}
