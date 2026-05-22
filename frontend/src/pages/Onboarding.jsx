import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  connectWA, verifyWA,
  genPairingCode, getPairingStatus, selectCompany,
  getLedgers, saveMappings,
} from '../api'

const STEPS = ['WhatsApp', 'Tally pairing', 'Ledger mappings']

export default function Onboarding() {
  const nav = useNavigate()
  const [step, setStep] = useState(0)

  return (
    <div className="mx-auto max-w-xl px-4 py-10">
      <h1 className="mb-2 text-2xl font-semibold">Set up Tally Co-pilot</h1>
      <ol className="mb-8 flex gap-2 text-sm">
        {STEPS.map((s, i) => (
          <li key={s} className={`flex-1 rounded px-3 py-1 ${i === step ? 'bg-slate-900 text-white' : i < step ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-600'}`}>
            {i + 1}. {s}
          </li>
        ))}
      </ol>

      <div className="rounded-lg bg-white p-6 shadow">
        {step === 0 && <Step1WA onDone={() => setStep(1)} />}
        {step === 1 && <Step2Tally onDone={() => setStep(2)} />}
        {step === 2 && <Step3Mappings onDone={() => nav('/dashboard')} />}
      </div>
    </div>
  )
}

function Step1WA({ onDone }) {
  const [phone, setPhone] = useState('+91MOCK12345')
  const [devOtp, setDevOtp] = useState(null)
  const [otp, setOtp] = useState('')
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)

  async function send() {
    setErr(null); setBusy(true)
    try {
      const r = await connectWA(phone)
      setDevOtp(r.dev_otp || null)
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }
  async function verify() {
    setErr(null); setBusy(true)
    try {
      await verifyWA(otp)
      onDone()
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  return (
    <div>
      <h2 className="mb-1 text-lg font-medium">Connect your WhatsApp number</h2>
      <p className="mb-4 text-sm text-slate-500">Invoices sent from this number will be auto-processed.</p>

      <label className="mb-1 block text-sm font-medium">Phone number (E.164)</label>
      <input value={phone} onChange={e => setPhone(e.target.value)}
        className="mb-3 w-full rounded border border-slate-300 px-3 py-2" />

      <button onClick={send} disabled={busy} className="mb-4 rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
        {busy ? 'Sending…' : devOtp ? 'Resend OTP' : 'Send OTP'}
      </button>

      {devOtp && (
        <div className="mb-3 rounded bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          DEV OTP: <span className="font-mono text-base">{devOtp}</span>
        </div>
      )}

      {(devOtp || true) && (
        <>
          <label className="mb-1 block text-sm font-medium">Enter OTP</label>
          <input value={otp} onChange={e => setOtp(e.target.value)} placeholder="6 digits"
            className="mb-3 w-full rounded border border-slate-300 px-3 py-2" />
          <button onClick={verify} disabled={busy || !otp} className="rounded bg-emerald-600 px-3 py-2 text-sm text-white disabled:opacity-50">
            Verify
          </button>
        </>
      )}

      {err && <div className="mt-3 rounded bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
    </div>
  )
}

function Step2Tally({ onDone }) {
  const [code, setCode] = useState(null)
  const [expiresIn, setExpiresIn] = useState(0)
  const [companies, setCompanies] = useState(null)
  const [selected, setSelected] = useState('')
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const pollRef = useRef(null)

  async function generate() {
    setErr(null); setBusy(true)
    try {
      const r = await genPairingCode()
      setCode(r.pairing_code)
      setExpiresIn(r.expires_in_seconds)
      startPolling()
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  function startPolling() {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const s = await getPairingStatus()
        if (s.is_paired) {
          setCompanies(s.company_names || [])
          setSelected((s.company_names || [])[0] || '')
          clearInterval(pollRef.current); pollRef.current = null
        } else if (typeof s.expires_in_seconds === 'number') {
          setExpiresIn(s.expires_in_seconds)
        }
      } catch { /* ignore */ }
    }, 3000)
  }

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  async function choose() {
    setErr(null); setBusy(true)
    try {
      await selectCompany(selected)
      onDone()
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  return (
    <div>
      <h2 className="mb-1 text-lg font-medium">Pair your Tally connector</h2>
      <p className="mb-4 text-sm text-slate-500">
        Run the connector on the machine where Tally is installed, then enter the code below into it.
      </p>

      {!code && (
        <button onClick={generate} disabled={busy} className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
          {busy ? 'Generating…' : 'Generate code'}
        </button>
      )}

      {code && !companies && (
        <>
          <div className="my-4 rounded bg-slate-100 p-6 text-center">
            <div className="text-xs uppercase tracking-wider text-slate-500">Pairing code</div>
            <div className="my-1 font-mono text-4xl tracking-widest">{code}</div>
            <div className="text-xs text-slate-500">Expires in {Math.max(0, Math.floor(expiresIn / 60))}m {Math.max(0, expiresIn % 60)}s</div>
          </div>
          <div className="text-sm text-slate-500">Waiting for the connector to pair…</div>
        </>
      )}

      {companies && (
        <div className="mt-4">
          <label className="mb-1 block text-sm font-medium">Select your company</label>
          <select value={selected} onChange={e => setSelected(e.target.value)}
            className="mb-3 w-full rounded border border-slate-300 px-3 py-2">
            {companies.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <button onClick={choose} disabled={busy || !selected} className="rounded bg-emerald-600 px-3 py-2 text-sm text-white disabled:opacity-50">
            Continue
          </button>
        </div>
      )}

      {err && <div className="mt-3 rounded bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
    </div>
  )
}

function Step3Mappings({ onDone }) {
  const [form, setForm] = useState({
    purchase_ledger: 'Purchases',
    cgst_ledger_format: 'CGST @ {rate}%',
    sgst_ledger_format: 'SGST @ {rate}%',
    igst_ledger_format: 'IGST @ {rate}%',
    auto_create_ledgers: true,
  })
  const [ledgers, setLedgers] = useState([])
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    getLedgers().then(r => setLedgers(r.ledgers || [])).catch(() => {})
  }, [])

  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  async function finish() {
    setErr(null); setBusy(true)
    try { await saveMappings(form); onDone() }
    catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  return (
    <div>
      <h2 className="mb-1 text-lg font-medium">Ledger mappings</h2>
      <p className="mb-4 text-sm text-slate-500">
        Defaults work for most setups. {ledgers.length > 0 && <span>Connector reported {ledgers.length} ledgers.</span>}
      </p>

      {['purchase_ledger', 'cgst_ledger_format', 'sgst_ledger_format', 'igst_ledger_format'].map(k => (
        <div key={k} className="mb-3">
          <label className="mb-1 block text-sm font-medium">{k}</label>
          <input value={form[k]} onChange={set(k)} className="w-full rounded border border-slate-300 px-3 py-2" />
        </div>
      ))}

      <label className="mb-4 inline-flex items-center gap-2 text-sm">
        <input type="checkbox" checked={form.auto_create_ledgers}
          onChange={e => setForm(f => ({ ...f, auto_create_ledgers: e.target.checked }))} />
        Auto-create missing ledgers in Tally
      </label>

      <div>
        <button onClick={finish} disabled={busy} className="rounded bg-emerald-600 px-3 py-2 text-sm text-white disabled:opacity-50">
          {busy ? 'Saving…' : 'Finish setup'}
        </button>
      </div>

      {err && <div className="mt-3 rounded bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
    </div>
  )
}
