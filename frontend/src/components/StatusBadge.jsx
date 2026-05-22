const COLORS = {
  pending:      'bg-slate-200 text-slate-700',
  processing:   'bg-blue-100 text-blue-800',
  pending_sync: 'bg-amber-100 text-amber-800',
  synced:       'bg-emerald-100 text-emerald-800',
  failed:       'bg-rose-100 text-rose-800',
}

export default function StatusBadge({ status, large = false }) {
  const cls = COLORS[status] || 'bg-slate-200 text-slate-700'
  const size = large ? 'px-3 py-1 text-sm' : 'px-2 py-0.5 text-xs'
  return (
    <span className={`inline-block rounded-full font-medium ${size} ${cls}`}>
      {status}
    </span>
  )
}
