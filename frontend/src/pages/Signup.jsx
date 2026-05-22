import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { signup } from '../api'

export default function Signup() {
  const nav = useNavigate()
  const [form, setForm] = useState({ first_name: '', email: '', password: '' })
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)

  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setErr(null); setBusy(true)
    try {
      const r = await signup(form)
      localStorage.setItem('token', r.token)
      nav('/onboarding')
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-lg bg-white p-6 shadow">
        <h1 className="mb-1 text-2xl font-semibold">Create account</h1>
        <p className="mb-6 text-sm text-slate-500">Get started with Tally Co-pilot</p>

        <label className="mb-1 block text-sm font-medium">First name</label>
        <input value={form.first_name} required onChange={set('first_name')}
          className="mb-3 w-full rounded border border-slate-300 px-3 py-2" />

        <label className="mb-1 block text-sm font-medium">Email</label>
        <input type="email" value={form.email} required onChange={set('email')}
          className="mb-3 w-full rounded border border-slate-300 px-3 py-2" />

        <label className="mb-1 block text-sm font-medium">Password</label>
        <input type="password" value={form.password} required minLength={6} onChange={set('password')}
          className="mb-4 w-full rounded border border-slate-300 px-3 py-2" />

        {err && <div className="mb-3 rounded bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}

        <button disabled={busy} className="w-full rounded bg-slate-900 py-2 text-white disabled:opacity-50">
          {busy ? 'Creating…' : 'Create account'}
        </button>

        <p className="mt-4 text-center text-sm text-slate-500">
          Already have an account? <Link to="/login" className="text-slate-900 underline">Sign in</Link>
        </p>
      </form>
    </div>
  )
}
