import { useState } from 'react'
import { Link } from 'react-router-dom'
import { forgotPassword } from '../api'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [devUrl, setDevUrl] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  async function submit(e) {
    e.preventDefault()
    setErr(null); setBusy(true)
    try {
      const r = await forgotPassword(email)
      setSent(true)
      if (r.dev_reset_url) setDevUrl(r.dev_reset_url)
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow">
        <h1 className="mb-1 text-2xl font-semibold">Forgot password</h1>
        <p className="mb-6 text-sm text-slate-500">We'll send a reset link to your email.</p>

        {sent ? (
          <div className="space-y-3">
            <div className="rounded bg-emerald-50 p-4 text-sm text-emerald-800">
              Check your inbox — reset link sent.
            </div>
            {devUrl && (
              <div className="rounded bg-amber-50 p-3 text-sm">
                <div className="mb-1 font-medium text-amber-800">DEV — reset link:</div>
                <a href={devUrl} className="break-all font-mono text-xs text-amber-900 underline">
                  {devUrl}
                </a>
              </div>
            )}
          </div>
        ) : (
          <form onSubmit={submit}>
            <label className="mb-1 block text-sm font-medium">Email</label>
            <input type="email" value={email} required onChange={e => setEmail(e.target.value)}
              className="mb-4 w-full rounded border border-slate-300 px-3 py-2" />
            {err && <div className="mb-3 rounded bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
            <button disabled={busy} className="w-full rounded bg-slate-900 py-2 text-white disabled:opacity-50">
              {busy ? 'Sending…' : 'Send reset link'}
            </button>
          </form>
        )}

        <p className="mt-4 text-center text-sm text-slate-500">
          <Link to="/login" className="text-slate-900 underline">Back to sign in</Link>
        </p>
      </div>
    </div>
  )
}
