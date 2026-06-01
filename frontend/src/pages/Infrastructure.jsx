import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  infraCatalog, infraTopology, infraProviders, infraCreate, infraUpdate,
  infraDelete, infraTest, infraRules, infraSaveRule, infraTelemetry, infraCallLog,
} from '../api'

const SURFACES = [
  { id: 'llm',          label: 'LLM',           hint: 'Invoice extraction model' },
  { id: 'object_store', label: 'Object storage',hint: 'Where uploaded files live' },
  { id: 'messenger',    label: 'Messenger',     hint: 'WhatsApp / SMS provider' },
]

const TABS = ['Topology', 'Providers', 'Routing', 'Telemetry', 'Call log']

export default function Infrastructure() {
  const [tab, setTab] = useState('Topology')

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <Link to="/dashboard" className="text-sm text-slate-500 hover:text-slate-900">← Back to dashboard</Link>
          <h1 className="mt-1 text-2xl font-semibold">Infrastructure</h1>
          <p className="text-sm text-slate-500">Manage every external provider this app talks to.</p>
        </div>
      </div>

      <div className="mb-6 flex gap-1 border-b">
        {TABS.map(t => (
          <button key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm transition border-b-2 -mb-px
              ${tab === t ? 'border-slate-900 font-medium text-slate-900'
                           : 'border-transparent text-slate-500 hover:text-slate-900'}`}>
            {t}
          </button>
        ))}
      </div>

      {tab === 'Topology'  && <TopologyTab  />}
      {tab === 'Providers' && <ProvidersTab />}
      {tab === 'Routing'   && <RoutingTab   />}
      {tab === 'Telemetry' && <TelemetryTab />}
      {tab === 'Call log'  && <CallLogTab   />}
    </div>
  )
}

// ============================================================================
// Topology
// ============================================================================
function TopologyTab() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    const tick = () => infraTopology().then(setData).catch(e => setErr(e.message))
    tick()
    const id = setInterval(tick, 5000)
    return () => clearInterval(id)
  }, [])

  if (err) return <div className="rounded bg-rose-50 p-3 text-sm text-rose-700">{err}</div>
  if (!data) return <div className="text-sm text-slate-500">Loading…</div>

  const bySurface = Object.fromEntries(data.surfaces.map(s => [s.surface, s]))

  return (
    <div className="space-y-4">
      {SURFACES.map(s => {
        const surface = bySurface[s.id]
        return (
          <div key={s.id} className="rounded-lg border bg-white p-4">
            <div className="mb-3 flex items-baseline gap-2">
              <h3 className="text-base font-medium">{s.label}</h3>
              <span className="text-xs text-slate-500">{s.hint}</span>
            </div>
            {!surface || surface.tasks.length === 0 ? (
              <div className="text-sm text-slate-400">No routing rules configured.</div>
            ) : (
              <div className="space-y-3">
                {surface.tasks.map((t, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-700">
                      {t.task}
                    </span>
                    <span className="text-xs text-slate-400">→</span>
                    <div className="flex flex-wrap items-center gap-2">
                      {t.weights.map(w => (
                        <div key={w.provider_id}
                          className="flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 text-xs">
                          <span className="font-medium text-emerald-800">{w.name}</span>
                          <span className="text-emerald-600">{w.weight}%</span>
                          <span className="text-emerald-500/70">({w.adapter_kind})</span>
                        </div>
                      ))}
                      {t.fallback.length > 0 && (
                        <>
                          <span className="text-xs text-slate-400">fallback →</span>
                          {t.fallback.map(f => (
                            <span key={f.provider_id} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                              {f.name}
                            </span>
                          ))}
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ============================================================================
// Providers
// ============================================================================
function ProvidersTab() {
  const [surface, setSurface] = useState('llm')
  const [providers, setProviders] = useState([])
  const [catalog, setCatalog] = useState([])
  const [editing, setEditing] = useState(null) // {kind, existing?}
  const [err, setErr] = useState(null)
  const [testResult, setTestResult] = useState({})

  const refresh = useCallback(() => {
    infraProviders(surface).then(r => setProviders(r.providers)).catch(e => setErr(e.message))
    infraCatalog(surface).then(r => setCatalog(r.kinds)).catch(e => setErr(e.message))
  }, [surface])

  useEffect(() => { refresh() }, [refresh])

  async function test(p) {
    setTestResult(prev => ({ ...prev, [p.id]: { loading: true } }))
    try {
      const r = await infraTest(p.id)
      setTestResult(prev => ({ ...prev, [p.id]: r }))
    } catch (e) {
      setTestResult(prev => ({ ...prev, [p.id]: { ok: false, message: e.message } }))
    }
  }

  async function toggle(p) {
    await infraUpdate(p.id, { enabled: !p.enabled })
    refresh()
  }

  async function remove(p) {
    if (!confirm(`Delete provider "${p.name}"?`)) return
    await infraDelete(p.id)
    refresh()
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-2">
        {SURFACES.map(s => (
          <button key={s.id} onClick={() => setSurface(s.id)}
            className={`rounded px-3 py-1 text-sm ${surface === s.id ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700'}`}>
            {s.label}
          </button>
        ))}
        <div className="flex-1" />
        <select value="" onChange={e => e.target.value && setEditing({ kind: e.target.value })}
          className="rounded border border-slate-300 px-2 py-1 text-sm">
          <option value="">+ Add provider…</option>
          {catalog.map(k => <option key={k.kind} value={k.kind}>{k.display_name}</option>)}
        </select>
      </div>

      {err && <div className="mb-3 rounded bg-rose-50 p-3 text-sm text-rose-700">{err}</div>}

      {providers.length === 0 ? (
        <div className="rounded border border-dashed p-8 text-center text-sm text-slate-400">
          No providers configured for this surface.
        </div>
      ) : (
        <div className="space-y-2">
          {providers.map(p => (
            <div key={p.id} className="rounded-lg border bg-white p-3">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`inline-block h-2 w-2 rounded-full ${p.enabled ? 'bg-emerald-500' : 'bg-slate-300'}`} />
                    <span className="font-medium">{p.name}</span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                      {p.adapter_kind}
                    </span>
                  </div>
                  <div className="mt-1 grid grid-cols-2 gap-x-4 text-xs text-slate-500">
                    {Object.entries(p.config).map(([k, v]) => (
                      <div key={k}><span className="text-slate-400">{k}:</span> <span className="text-slate-700 font-mono">{String(v)}</span></div>
                    ))}
                  </div>
                  {testResult[p.id] && (
                    <div className={`mt-2 text-xs ${testResult[p.id].loading ? 'text-slate-500' :
                      testResult[p.id].ok ? 'text-emerald-700' : 'text-rose-700'}`}>
                      {testResult[p.id].loading ? 'Testing…' : (testResult[p.id].ok ? '✓ ' : '✗ ') + (testResult[p.id].message || '')}
                    </div>
                  )}
                </div>
                <div className="flex gap-1 text-xs">
                  <button onClick={() => test(p)} className="rounded border px-2 py-1 hover:bg-slate-50">Test</button>
                  <button onClick={() => setEditing({ kind: p.adapter_kind, existing: p })} className="rounded border px-2 py-1 hover:bg-slate-50">Edit</button>
                  <button onClick={() => toggle(p)} className="rounded border px-2 py-1 hover:bg-slate-50">{p.enabled ? 'Disable' : 'Enable'}</button>
                  <button onClick={() => remove(p)} className="rounded border border-rose-200 px-2 py-1 text-rose-700 hover:bg-rose-50">Delete</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && (
        <ProviderForm
          kind={editing.kind}
          surface={surface}
          existing={editing.existing}
          catalog={catalog}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); refresh() }}
        />
      )}
    </div>
  )
}

function ProviderForm({ kind, surface, existing, catalog, onClose, onSaved }) {
  const kindMeta = catalog.find(k => k.kind === kind)
  const fields = kindMeta?.fields || []
  const [name, setName] = useState(existing?.name || `${kind}-${Math.random().toString(36).slice(2, 6)}`)
  const initialConfig = Object.fromEntries(fields.map(f => [f.name, existing?.config?.[f.name] ?? f.default ?? '']))
  const [config, setConfig] = useState(initialConfig)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  async function save() {
    setErr(null); setBusy(true)
    try {
      const body = { surface, adapter_kind: kind, name, config }
      if (existing) await infraUpdate(existing.id, { name, config })
      else await infraCreate(body)
      onSaved()
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl" onClick={e => e.stopPropagation()}>
        <h3 className="mb-1 text-lg font-semibold">
          {existing ? 'Edit' : 'Add'} provider · {kindMeta?.display_name}
        </h3>
        <p className="mb-4 text-xs text-slate-500">surface = {surface}</p>

        <label className="mb-1 block text-sm font-medium">Name</label>
        <input value={name} onChange={e => setName(e.target.value)}
          className="mb-3 w-full rounded border border-slate-300 px-3 py-2 text-sm" />

        {fields.map(f => (
          <div key={f.name} className="mb-3">
            <label className="mb-1 block text-sm font-medium">{f.label}</label>
            <input
              type={f.type === 'password' ? 'password' : 'text'}
              value={config[f.name] ?? ''}
              onChange={e => setConfig(c => ({ ...c, [f.name]: e.target.value }))}
              placeholder={f.default || ''}
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm font-mono" />
            {f.help && <div className="mt-1 text-xs text-slate-500">{f.help}</div>}
          </div>
        ))}

        {err && <div className="mb-3 rounded bg-rose-50 p-2 text-sm text-rose-700">{err}</div>}

        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="rounded border px-3 py-1 text-sm">Cancel</button>
          <button onClick={save} disabled={busy} className="rounded bg-slate-900 px-3 py-1 text-sm text-white disabled:opacity-50">
            {busy ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ============================================================================
// Routing
// ============================================================================
function RoutingTab() {
  const [surface, setSurface] = useState('llm')
  const [task, setTask] = useState('extract_invoice')
  const [providers, setProviders] = useState([])
  const [rule, setRule] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const refresh = useCallback(() => {
    infraProviders(surface).then(r => setProviders(r.providers.filter(p => p.enabled))).catch(e => setErr(e.message))
    infraRules(surface).then(r => {
      const t = (surface === 'llm') ? task : '*'
      const match = r.rules.find(x => x.surface === surface && x.task === t)
      setRule(match || { surface, task: t, weights: [], fallback: [] })
    })
  }, [surface, task])

  useEffect(() => { refresh() }, [refresh])

  function setWeight(provider_id, weight) {
    setRule(r => {
      const weights = [...(r.weights || [])]
      const i = weights.findIndex(w => w.provider_id === provider_id)
      if (i >= 0) {
        if (weight <= 0) weights.splice(i, 1)
        else weights[i] = { provider_id, weight }
      } else if (weight > 0) {
        weights.push({ provider_id, weight })
      }
      return { ...r, weights }
    })
  }

  function toggleFallback(provider_id) {
    setRule(r => {
      const fb = r.fallback || []
      return { ...r, fallback: fb.includes(provider_id) ? fb.filter(x => x !== provider_id) : [...fb, provider_id] }
    })
  }

  async function save() {
    setErr(null); setBusy(true)
    try {
      await infraSaveRule({
        surface: rule.surface, task: rule.task,
        weights: rule.weights, fallback: rule.fallback,
        budget_cap_usd_month: rule.budget_cap_usd_month || null,
        max_rpm: rule.max_rpm || null,
      })
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  if (!rule) return <div className="text-sm text-slate-500">Loading…</div>

  const total = (rule.weights || []).reduce((s, w) => s + (w.weight || 0), 0)

  return (
    <div>
      <div className="mb-4 flex items-center gap-2">
        {SURFACES.map(s => (
          <button key={s.id} onClick={() => setSurface(s.id)}
            className={`rounded px-3 py-1 text-sm ${surface === s.id ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700'}`}>
            {s.label}
          </button>
        ))}
        <div className="flex-1" />
        {surface === 'llm' && (
          <select value={task} onChange={e => setTask(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm">
            <option value="extract_invoice">extract_invoice</option>
            <option value="*">* (any task)</option>
          </select>
        )}
      </div>

      <div className="rounded-lg border bg-white p-4">
        <h3 className="mb-3 text-sm font-medium">Weights (total {total})</h3>
        {providers.length === 0 ? (
          <div className="text-sm text-slate-400">No enabled providers on this surface. Add one in the Providers tab.</div>
        ) : (
          <div className="space-y-2">
            {providers.map(p => {
              const w = rule.weights.find(x => x.provider_id === p.id)?.weight || 0
              return (
                <div key={p.id} className="flex items-center gap-3">
                  <span className="w-48 truncate text-sm">{p.name} <span className="text-xs text-slate-400">({p.adapter_kind})</span></span>
                  <input type="range" min="0" max="100" value={w}
                    onChange={e => setWeight(p.id, Number(e.target.value))}
                    className="flex-1" />
                  <span className="w-12 text-right font-mono text-sm">{w}%</span>
                </div>
              )
            })}
          </div>
        )}

        <h3 className="mb-2 mt-6 text-sm font-medium">Fallback chain (tried in order on error)</h3>
        <div className="flex flex-wrap gap-2">
          {providers.map(p => {
            const inFb = (rule.fallback || []).includes(p.id)
            return (
              <button key={p.id} onClick={() => toggleFallback(p.id)}
                className={`rounded border px-2 py-1 text-xs ${inFb ? 'border-amber-400 bg-amber-50 text-amber-800' : 'border-slate-300 text-slate-600'}`}>
                {p.name}
              </button>
            )
          })}
        </div>

        <div className="mt-6 flex gap-2">
          <input type="number" placeholder="Budget cap USD/month" value={rule.budget_cap_usd_month || ''}
            onChange={e => setRule(r => ({ ...r, budget_cap_usd_month: e.target.value ? Number(e.target.value) : null }))}
            className="w-44 rounded border border-slate-300 px-2 py-1 text-sm" />
          <input type="number" placeholder="Max RPM" value={rule.max_rpm || ''}
            onChange={e => setRule(r => ({ ...r, max_rpm: e.target.value ? Number(e.target.value) : null }))}
            className="w-28 rounded border border-slate-300 px-2 py-1 text-sm" />
          <div className="flex-1" />
          <button onClick={save} disabled={busy} className="rounded bg-emerald-600 px-3 py-1 text-sm text-white disabled:opacity-50">
            {busy ? 'Saving…' : 'Save routing rule'}
          </button>
        </div>
        {err && <div className="mt-3 rounded bg-rose-50 p-2 text-sm text-rose-700">{err}</div>}
      </div>
    </div>
  )
}

// ============================================================================
// Telemetry
// ============================================================================
function TelemetryTab() {
  const [data, setData] = useState(null)
  const [hours, setHours] = useState(24)
  const [err, setErr] = useState(null)

  useEffect(() => {
    const tick = () => infraTelemetry(null, hours).then(setData).catch(e => setErr(e.message))
    tick()
    const id = setInterval(tick, 5000)
    return () => clearInterval(id)
  }, [hours])

  if (err) return <div className="rounded bg-rose-50 p-3 text-sm text-rose-700">{err}</div>
  if (!data) return <div className="text-sm text-slate-500">Loading…</div>

  const grouped = {}
  for (const r of data.per_provider) {
    grouped[r.surface] = grouped[r.surface] || []
    grouped[r.surface].push(r)
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-2">
        <span className="text-sm text-slate-500">Window:</span>
        {[1, 6, 24, 168, 720].map(h => (
          <button key={h} onClick={() => setHours(h)}
            className={`rounded px-2 py-1 text-xs ${hours === h ? 'bg-slate-900 text-white' : 'bg-slate-100'}`}>
            {h < 24 ? `${h}h` : `${h/24}d`}
          </button>
        ))}
      </div>

      {SURFACES.map(s => {
        const rows = grouped[s.id] || []
        return (
          <div key={s.id} className="mb-4 rounded-lg border bg-white">
            <div className="border-b px-4 py-2 text-sm font-medium">{s.label}</div>
            {rows.length === 0 ? (
              <div className="p-4 text-sm text-slate-400">No calls in the last {hours}h.</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase text-slate-500">
                  <tr><th className="px-4 py-1.5">Provider</th>
                      <th className="px-4 py-1.5 text-right">Calls</th>
                      <th className="px-4 py-1.5 text-right">Success</th>
                      <th className="px-4 py-1.5 text-right">Errors</th>
                      <th className="px-4 py-1.5 text-right">Avg ms</th>
                      <th className="px-4 py-1.5 text-right">Cost USD</th></tr>
                </thead>
                <tbody>
                  {rows.map(r => (
                    <tr key={r.provider_id} className="border-t">
                      <td className="px-4 py-1.5">{r.adapter_kind}</td>
                      <td className="px-4 py-1.5 text-right tabular-nums">{r.calls}</td>
                      <td className="px-4 py-1.5 text-right tabular-nums text-emerald-700">{r.successes}</td>
                      <td className="px-4 py-1.5 text-right tabular-nums text-rose-700">{r.errors}</td>
                      <td className="px-4 py-1.5 text-right tabular-nums">{r.avg_duration_ms.toFixed(0)}</td>
                      <td className="px-4 py-1.5 text-right tabular-nums">${r.total_cost_usd.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ============================================================================
// Call log
// ============================================================================
function CallLogTab() {
  const [filter, setFilter] = useState({ surface: '', success: '' })
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    const params = {}
    if (filter.surface) params.surface = filter.surface
    if (filter.success !== '') params.success = filter.success
    params.limit = 100
    infraCallLog(params).then(setData).catch(e => setErr(e.message))
  }, [filter])

  if (err) return <div className="rounded bg-rose-50 p-3 text-sm text-rose-700">{err}</div>

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <select value={filter.surface} onChange={e => setFilter(f => ({ ...f, surface: e.target.value }))}
          className="rounded border border-slate-300 px-2 py-1 text-sm">
          <option value="">All surfaces</option>
          {SURFACES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
        </select>
        <select value={filter.success} onChange={e => setFilter(f => ({ ...f, success: e.target.value }))}
          className="rounded border border-slate-300 px-2 py-1 text-sm">
          <option value="">All</option>
          <option value="true">Success only</option>
          <option value="false">Errors only</option>
        </select>
        <div className="ml-auto text-xs text-slate-500">{data ? `${data.items.length} of ${data.total}` : ''}</div>
      </div>

      <div className="overflow-hidden rounded-lg border bg-white">
        {!data ? <div className="p-4 text-sm text-slate-500">Loading…</div> :
        data.items.length === 0 ? <div className="p-4 text-sm text-slate-400">No calls match.</div> :
          <table className="w-full text-xs">
            <thead className="text-left uppercase text-slate-500">
              <tr>
                <th className="px-3 py-1.5">When</th>
                <th className="px-3 py-1.5">Surface</th>
                <th className="px-3 py-1.5">Task</th>
                <th className="px-3 py-1.5">Provider</th>
                <th className="px-3 py-1.5 text-right">ms</th>
                <th className="px-3 py-1.5 text-right">Tokens in/out</th>
                <th className="px-3 py-1.5 text-right">Cost</th>
                <th className="px-3 py-1.5">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map(r => (
                <tr key={r.id} className="border-t">
                  <td className="px-3 py-1.5 text-slate-500">{r.started_at?.slice(0, 19).replace('T', ' ')}</td>
                  <td className="px-3 py-1.5">{r.surface}</td>
                  <td className="px-3 py-1.5 font-mono text-slate-600">{r.task}</td>
                  <td className="px-3 py-1.5">{r.adapter_kind}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{r.duration_ms}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-slate-500">
                    {(r.request_tokens ?? '-') + ' / ' + (r.response_tokens ?? '-')}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{r.cost_usd ? `$${r.cost_usd.toFixed(4)}` : '—'}</td>
                  <td className="px-3 py-1.5">
                    {r.success
                      ? <span className="text-emerald-700">OK</span>
                      : <span className="text-rose-700" title={r.error}>ERR</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        }
      </div>
    </div>
  )
}
