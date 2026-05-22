import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import ActionDetail from './pages/ActionDetail'
import ProtectedRoute from './components/ProtectedRoute'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login"       element={<Login />} />
        <Route path="/signup"      element={<Signup />} />
        <Route path="/onboarding"  element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
        <Route path="/dashboard"   element={<ProtectedRoute requireOnboarded><Dashboard /></ProtectedRoute>} />
        <Route path="/actions/:id" element={<ProtectedRoute requireOnboarded><ActionDetail /></ProtectedRoute>} />
        <Route path="*"            element={<Navigate to="/dashboard" />} />
      </Routes>
    </BrowserRouter>
  )
}
