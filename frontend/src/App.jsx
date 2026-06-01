import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import ActionDetail from './pages/ActionDetail'
import Infrastructure from './pages/Infrastructure'
import Settings from './pages/Settings'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import ProtectedRoute from './components/ProtectedRoute'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"                element={<Landing />} />
        <Route path="/login"           element={<Login />} />
        <Route path="/signup"          element={<Signup />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password"  element={<ResetPassword />} />
        <Route path="/onboarding"      element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
        <Route path="/dashboard"       element={<ProtectedRoute requireOnboarded><Dashboard /></ProtectedRoute>} />
        <Route path="/actions/:id"     element={<ProtectedRoute requireOnboarded><ActionDetail /></ProtectedRoute>} />
        <Route path="/settings/infra"  element={<ProtectedRoute requireOnboarded><Infrastructure /></ProtectedRoute>} />
        <Route path="/settings"        element={<ProtectedRoute requireOnboarded><Settings /></ProtectedRoute>} />
        <Route path="*"                element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  )
}
