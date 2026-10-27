import { createContext, useCallback, useContext, useEffect, useState } from 'react'

export function Button({ variant = 'primary', className = '', ...props }) {
  const styles = {
    primary: 'bg-room text-white hover:bg-room-deep',
    quiet: 'bg-sheet text-ink border border-line hover:border-room',
    danger: 'bg-stamp text-white hover:brightness-110',
    brass: 'bg-brass text-white hover:brightness-110',
  }
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}
      {...props}
    />
  )
}

// Open book seen from above: the brand glyph beside "Reading Room".
export function BrandMark({ className = 'h-6 w-6' }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" fill="none" strokeWidth="1.8" strokeLinejoin="round">
      <path d="M12 6.5C10 5 7 4.5 3 5v13c4-.5 7 0 9 1.5V6.5Z" fill="var(--color-room)" stroke="var(--color-room)" />
      <path d="M12 6.5c2-1.5 5-2 9-1.5v13c-4-.5-7 0-9 1.5V6.5Z" fill="var(--color-room-soft)" stroke="var(--color-room)" />
      <path d="M15 9.5c1.5-.4 2.7-.5 4-.4" stroke="var(--color-brass)" strokeLinecap="round" />
    </svg>
  )
}

export function PageHeader({ title, children, intro }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-3xl font-semibold text-room-deep">{title}</h1>
        {intro && <p className="mt-1 max-w-2xl text-ink-soft">{intro}</p>}
      </div>
      {children}
    </header>
  )
}

export function Panel({ title, action, children, className = '' }) {
  return (
    <section className={`rounded-lg border border-line bg-sheet ${className}`}>
      {title && (
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 className="text-lg font-semibold">{title}</h2>
          {action}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

export function Empty({ children }) {
  return <p className="rounded-md border border-dashed border-line px-4 py-8 text-center text-ink-soft">{children}</p>
}

export function Loading({ label = 'Loading' }) {
  return <p className="animate-pulse py-8 text-center text-ink-soft" role="status">{label}…</p>
}

export function ErrorNote({ error }) {
  if (!error) return null
  return <p className="rounded-md bg-stamp-soft px-3 py-2 text-sm text-stamp" role="alert">{error}</p>
}

const LEVEL = {
  instant: { label: 'Borrows instantly', cls: 'bg-room-soft text-room-deep' },
  approval: { label: 'Needs approval', cls: 'bg-brass-soft text-[#7a5a17]' },
  blocked: { label: 'Borrowing blocked', cls: 'bg-stamp-soft text-stamp' },
}

export function TrustBadge({ score, level, compact = false }) {
  const l = LEVEL[level] || LEVEL.instant
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${l.cls}`}>
      <span className="tabular-nums">Trust {score}</span>
      {!compact && <span className="font-medium opacity-80">· {l.label}</span>}
    </span>
  )
}

export function StatusPill({ status, overdue }) {
  const map = {
    borrowed: 'bg-room-soft text-room-deep', pending: 'bg-brass-soft text-[#7a5a17]',
    returned: 'bg-paper text-ink-soft border border-line', rejected: 'bg-stamp-soft text-stamp',
    unpaid: 'bg-stamp-soft text-stamp', paid: 'bg-room-soft text-room-deep', waived: 'bg-paper text-ink-soft border border-line',
  }
  const text = overdue ? `Overdue ${overdue}d` : status
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${overdue ? map.rejected : map[status]}`}>{text}</span>
}

export function Stat({ label, value, tone = 'ink' }) {
  const color = { ink: 'text-ink', stamp: 'text-stamp', brass: 'text-brass', room: 'text-room' }[tone]
  return (
    <div className="rounded-lg border border-line bg-sheet px-4 py-3">
      <div className={`font-book text-3xl font-semibold tabular-nums ${color}`}>{value}</div>
      <div className="text-sm text-ink-soft">{label}</div>
    </div>
  )
}

// ---- Toasts ----
const ToastContext = createContext(() => {})

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const push = useCallback((message, tone = 'ok') => {
    const id = Math.random().toString(36).slice(2)
    setToasts((t) => [...t, { id, message, tone }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200)
  }, [])
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast-enter rounded-md px-4 py-3 text-sm font-medium text-white shadow-lg ${t.tone === 'error' ? 'bg-stamp' : 'bg-room-deep'}`}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
export const useToast = () => useContext(ToastContext)

// ---- Data loading hook: { data, error, loading, reload } ----
export function useApi(loader, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const run = useCallback(() => {
    setState((s) => ({ ...s, loading: true, error: null }))
    loader().then((data) => setState({ data, error: null, loading: false }))
      .catch((e) => setState({ data: null, error: e.message, loading: false }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => { run() }, [run])
  return { ...state, reload: run }
}
