const BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api'
const tok = () => localStorage.getItem('token')
const jh = () => ({ 'Authorization': `Bearer ${tok()}`, 'Content-Type': 'application/json' })
const fh = () => ({ 'Authorization': `Bearer ${tok()}` })

async function _json(r) {
  const t = await r.text()
  let body = {}
  try { body = t ? JSON.parse(t) : {} } catch { body = { _raw: t } }
  if (!r.ok) {
    const err = new Error(body.detail || `HTTP ${r.status}`)
    err.status = r.status
    err.body = body
    throw err
  }
  return body
}

export const signup           = d  => fetch(`${BASE}/auth/signup`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(d) }).then(_json)
export const login            = d  => fetch(`${BASE}/auth/login`,  { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(d) }).then(_json)
export const getMe            = () => fetch(`${BASE}/auth/me`, { headers:jh() }).then(_json)

export const connectWA        = p  => fetch(`${BASE}/onboarding/whatsapp/connect`,           { method:'POST', headers:jh(), body:JSON.stringify({phone_number:p}) }).then(_json)
export const verifyWA         = o  => fetch(`${BASE}/onboarding/whatsapp/verify`,             { method:'POST', headers:jh(), body:JSON.stringify({otp:o}) }).then(_json)
export const genPairingCode   = () => fetch(`${BASE}/onboarding/tally/generate-pairing-code`, { method:'POST', headers:jh() }).then(_json)
export const getPairingStatus = () => fetch(`${BASE}/onboarding/tally/pairing-status`,        { headers:jh() }).then(_json)
export const selectCompany    = n  => fetch(`${BASE}/onboarding/tally/select-company`,        { method:'POST', headers:jh(), body:JSON.stringify({company_name:n}) }).then(_json)
export const getLedgers       = () => fetch(`${BASE}/onboarding/tally/ledgers`,               { headers:jh() }).then(_json)
export const saveMappings     = d  => fetch(`${BASE}/onboarding/tally/save-mappings`,         { method:'POST', headers:jh(), body:JSON.stringify(d) }).then(_json)

export const getActions       = (params={}) => {
  const q = new URLSearchParams(params).toString()
  return fetch(`${BASE}/actions${q?`?${q}`:''}`, { headers:jh() }).then(_json)
}
export const getAction        = id     => fetch(`${BASE}/actions/${id}`,         { headers:jh() }).then(_json)
export const getActionStats   = ()     => fetch(`${BASE}/actions/stats`,          { headers:jh() }).then(_json)
export const retryAction      = id     => fetch(`${BASE}/actions/${id}/retry`,    { method:'POST', headers:jh() }).then(_json)
export const approveAction    = id     => fetch(`${BASE}/actions/${id}/approve`,  { method:'POST', headers:jh() }).then(_json)
export const rejectAction     = id     => fetch(`${BASE}/actions/${id}/reject`,   { method:'POST', headers:jh() }).then(_json)
export const updateExtracted  = (id,d) => fetch(`${BASE}/actions/${id}/extracted`,{ method:'PATCH', headers:jh(), body:JSON.stringify({extracted_invoice:d}) }).then(_json)
export const exportCsvUrl     = (params={}) => {
  const q = new URLSearchParams(params).toString()
  return `${BASE}/actions/export.csv${q?`?${q}`:''}`
}

export const uploadDocument   = file => {
  const f = new FormData()
  f.append('file', file); f.append('source', 'dashboard')
  return fetch(`${BASE}/documents/upload`, { method:'POST', headers:fh(), body:f }).then(_json)
}
export const documentFileUrl  = id => `${BASE}/documents/${id}/file`

// Auth extras
export const verifyEmail      = (otp) => fetch(`${BASE}/auth/verify-email`, { method:'POST', headers:jh(), body:JSON.stringify({otp}) }).then(_json)
export const resendOtp        = ()    => fetch(`${BASE}/auth/resend-otp`,    { method:'POST', headers:jh() }).then(_json)
export const forgotPassword   = (email) => fetch(`${BASE}/auth/forgot-password`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email}) }).then(_json)
export const resetPassword    = (token, new_password) => fetch(`${BASE}/auth/reset-password`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({token, new_password}) }).then(_json)

// Settings
export const getSettings      = ()    => fetch(`${BASE}/settings`,                { headers:jh() }).then(_json)
export const saveTallySettings= d     => fetch(`${BASE}/settings/tally`,          { method:'PUT', headers:jh(), body:JSON.stringify(d) }).then(_json)
export const saveReviewMode   = v     => fetch(`${BASE}/settings/review-mode`,    { method:'PUT', headers:jh(), body:JSON.stringify({require_review:v}) }).then(_json)
export const connectWASetting = p     => fetch(`${BASE}/settings/whatsapp/connect`, { method:'POST', headers:jh(), body:JSON.stringify({phone_number:p}) }).then(_json)
export const verifyWASetting  = otp   => fetch(`${BASE}/settings/whatsapp/verify`,  { method:'POST', headers:jh(), body:JSON.stringify({otp}) }).then(_json)

export const mockIncoming     = (file, phone) => {
  const f = new FormData()
  f.append('file', file); f.append('sender_phone', phone)
  return fetch(`${BASE}/mock/whatsapp/incoming`, { method:'POST', body:f }).then(_json)
}
export const getMockWALog     = () => fetch(`${BASE}/mock/whatsapp/send-log`).then(_json)

// Infrastructure control plane
export const infraCatalog     = (surface)  => fetch(`${BASE}/infra/catalog${surface?`?surface=${surface}`:''}`, { headers:jh() }).then(_json)
export const infraTopology    = ()         => fetch(`${BASE}/infra/topology`, { headers:jh() }).then(_json)
export const infraProviders   = (surface)  => fetch(`${BASE}/infra/providers${surface?`?surface=${surface}`:''}`, { headers:jh() }).then(_json)
export const infraCreate      = (body)     => fetch(`${BASE}/infra/providers`, { method:'POST', headers:jh(), body:JSON.stringify(body) }).then(_json)
export const infraUpdate      = (id, body) => fetch(`${BASE}/infra/providers/${id}`, { method:'PATCH', headers:jh(), body:JSON.stringify(body) }).then(_json)
export const infraDelete      = (id)       => fetch(`${BASE}/infra/providers/${id}`, { method:'DELETE', headers:jh() }).then(_json)
export const infraTest        = (id)       => fetch(`${BASE}/infra/providers/${id}/test`, { method:'POST', headers:jh() }).then(_json)
export const infraRules       = (surface)  => fetch(`${BASE}/infra/rules${surface?`?surface=${surface}`:''}`, { headers:jh() }).then(_json)
export const infraSaveRule    = (body)     => fetch(`${BASE}/infra/rules`, { method:'PUT', headers:jh(), body:JSON.stringify(body) }).then(_json)
export const infraTelemetry   = (surface, hours=24) => fetch(`${BASE}/infra/telemetry?hours=${hours}${surface?`&surface=${surface}`:''}`, { headers:jh() }).then(_json)
export const infraCallLog     = (q={})     => {
  const params = new URLSearchParams(q).toString()
  return fetch(`${BASE}/infra/call-log${params?`?${params}`:''}`, { headers:jh() }).then(_json)
}
