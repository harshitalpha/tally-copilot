const BASE = 'http://localhost:8000/api'
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

export const getActions       = (q='') => fetch(`${BASE}/actions?${q}`, { headers:jh() }).then(_json)
export const getAction        = id     => fetch(`${BASE}/actions/${id}`, { headers:jh() }).then(_json)

export const uploadDocument   = file => {
  const f = new FormData()
  f.append('file', file); f.append('source', 'dashboard')
  return fetch(`${BASE}/documents/upload`, { method:'POST', headers:fh(), body:f }).then(_json)
}
export const documentFileUrl  = id => `${BASE}/documents/${id}/file`

export const mockIncoming     = (file, phone) => {
  const f = new FormData()
  f.append('file', file); f.append('sender_phone', phone)
  return fetch(`${BASE}/mock/whatsapp/incoming`, { method:'POST', body:f }).then(_json)
}
export const getMockWALog     = () => fetch(`${BASE}/mock/whatsapp/send-log`).then(_json)
