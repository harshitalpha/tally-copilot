import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { getMe } from '../api'

export default function ProtectedRoute({ children, requireOnboarded = false }) {
  const location = useLocation()
  const [state, setState] = useState({ loading: true, user: null })

  useEffect(() => {
    if (!localStorage.getItem('token')) {
      setState({ loading: false, user: null })
      return
    }
    let cancelled = false
    getMe()
      .then(user => { if (!cancelled) setState({ loading: false, user }) })
      .catch(() => {
        if (cancelled) return
        localStorage.removeItem('token')
        setState({ loading: false, user: null })
      })
    return () => { cancelled = true }
  }, [location.pathname])

  if (state.loading) {
    return <div className="flex h-screen items-center justify-center text-slate-500">Loading…</div>
  }
  if (!state.user) return <Navigate to="/login" replace />
  if (requireOnboarded && !state.user.is_onboarded) return <Navigate to="/onboarding" replace />
  if (!requireOnboarded && state.user.is_onboarded && location.pathname === '/onboarding') {
    return <Navigate to="/dashboard" replace />
  }
  return children
}
