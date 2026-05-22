import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { login } from '../api'

export default function Login() {
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setErr(null); setBusy(true)
    try {
      const r = await login({ email, password })
      localStorage.setItem('token', r.token)
      nav(r.user.is_onboarded ? '/dashboard' : '/onboarding')
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-lg bg-white p-6 shadow">
        <h1 className="mb-1 text-2xl font-semibold">Sign in</h1>
        <p className="mb-6 text-sm text-slate-500">Welcome back to Tally Co-pilot</p>

        <label className="mb-1 block text-sm font-medium">Email</label>
        <input
          type="email" value={email} required onChange={e => setEmail(e.target.value)}
          className="mb-3 w-full rounded border border-slate-300 px-3 py-2"
        />

        <label className="mb-1 block text-sm font-medium">Password</label>
        <input
          type="password" value={password} required onChange={e => setPassword(e.target.value)}
          className="mb-4 w-full rounded border border-slate-300 px-3 py-2"
        />

        {err && <div className="mb-3 rounded bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}

        <button disabled={busy} className="w-full rounded bg-slate-900 py-2 text-white disabled:opacity-50">
          {busy ? 'Signing in…' : 'Sign in'}
        </button>

        <p className="mt-4 text-center text-sm text-slate-500">
          No account? <Link to="/signup" className="text-slate-900 underline">Sign up</Link>
        </p>
      </form>
    </div>
  )
}
