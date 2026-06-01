import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { signup, verifyEmail, resendOtp } from '../api'

export default function Signup() {
  const nav = useNavigate()
  const [form, setForm] = useState({ first_name: '', email: '', password: '' })
  const [step, setStep] = useState('form')  // 'form' | 'verify'
  const [otp, setOtp] = useState('')
  const [devOtp, setDevOtp] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)

  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  async function submitForm(e) {
    e.preventDefault()
    setErr(null); setBusy(true)
    try {
      const r = await signup(form)
      localStorage.setItem('token', r.token)
      setDevOtp(r.dev_otp || null)
      if (r.user.email_verified) {
        nav('/onboarding')
      } else {
        setStep('verify')
      }
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  async function submitOtp(e) {
    e.preventDefault()
    setErr(null); setBusy(true)
    try {
      await verifyEmail(otp)
      nav('/onboarding')
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  async function resend() {
    try {
      const r = await resendOtp()
      if (r.dev_otp) setDevOtp(r.dev_otp)
    } catch { /* ignore */ }
  }

  if (step === 'verify') {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <form onSubmit={submitOtp} className="w-full max-w-sm rounded-lg bg-white p-6 shadow">
          <h1 className="mb-1 text-2xl font-semibold">Verify your email</h1>
          <p className="mb-1 text-sm text-slate-500">
            We sent a 6-digit code to <strong>{form.email}</strong>.
          </p>
          {devOtp && (
            <div className="mb-4 rounded bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              DEV OTP: <span className="font-mono text-base font-bold">{devOtp}</span>
            </div>
          )}
          <input value={otp} required onChange={e => setOtp(e.target.value)}
            placeholder="6-digit code"
            className="mb-4 w-full rounded border border-slate-300 px-3 py-2 text-center text-xl tracking-widest" />
          {err && <div className="mb-3 rounded bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
          <button disabled={busy} className="w-full rounded bg-slate-900 py-2 text-white disabled:opacity-50">
            {busy ? 'Verifying…' : 'Verify email'}
          </button>
          <p className="mt-3 text-center text-sm text-slate-500">
            Didn't get it?{' '}
            <button type="button" onClick={resend} className="text-slate-900 underline">Resend</button>
          </p>
        </form>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={submitForm} className="w-full max-w-sm rounded-lg bg-white p-6 shadow">
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
          {busy ? 'Creating account…' : 'Create account'}
        </button>

        <p className="mt-4 text-center text-sm text-slate-500">
          Already have an account?{' '}
          <Link to="/login" className="text-slate-900 underline">Sign in</Link>
        </p>
      </form>
    </div>
  )
}
