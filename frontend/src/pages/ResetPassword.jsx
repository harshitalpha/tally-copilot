import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { resetPassword } from '../api'

export default function ResetPassword() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const nav = useNavigate()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [err, setErr] = useState(null)

  async function submit(e) {
    e.preventDefault()
    if (password !== confirm) { setErr('Passwords do not match'); return }
    if (password.length < 6) { setErr('Minimum 6 characters'); return }
    setErr(null); setBusy(true)
    try {
      await resetPassword(token, password)
      setDone(true)
      setTimeout(() => nav('/login'), 2000)
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  if (!token) return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="rounded-lg bg-rose-50 p-6 text-sm text-rose-700">
        Invalid reset link. <Link to="/forgot-password" className="underline">Request a new one</Link>.
      </div>
    </div>
  )

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow">
        <h1 className="mb-1 text-2xl font-semibold">Set new password</h1>
        <p className="mb-6 text-sm text-slate-500">Choose a strong password for your account.</p>

        {done ? (
          <div className="rounded bg-emerald-50 p-4 text-sm text-emerald-800">
            Password updated! Redirecting to sign in…
          </div>
        ) : (
          <form onSubmit={submit}>
            <label className="mb-1 block text-sm font-medium">New password</label>
            <input type="password" value={password} required minLength={6}
              onChange={e => setPassword(e.target.value)}
              className="mb-3 w-full rounded border border-slate-300 px-3 py-2" />
            <label className="mb-1 block text-sm font-medium">Confirm password</label>
            <input type="password" value={confirm} required minLength={6}
              onChange={e => setConfirm(e.target.value)}
              className="mb-4 w-full rounded border border-slate-300 px-3 py-2" />
            {err && <div className="mb-3 rounded bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
            <button disabled={busy} className="w-full rounded bg-slate-900 py-2 text-white disabled:opacity-50">
              {busy ? 'Updating…' : 'Update password'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
