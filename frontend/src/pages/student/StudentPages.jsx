import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtDate, fmtDateTime } from '../../api/client'
import BookCard from '../../components/BookCard'
import RichText from '../../components/RichText'
import {
  Button, Empty, ErrorNote, Loading, PageHeader, Panel, StatusPill, TrustBadge, useApi, useToast,
} from '../../components/ui'
import { motifClass } from '../../lib/categories'

function useBorrow(onDone) {
  const toast = useToast()
  return async (book) => {
    try {
      const res = await api('/loans', { method: 'POST', body: { book_id: book.id } })
      toast(res.message)
      onDone?.()
      return res
    } catch (e) {
      toast(e.message, 'error')
      return null
    }
  }
}

function TrustLine() {
  const { data } = useApi(() => api('/auth/me/trust'))
  if (!data) return null
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm text-ink-soft">
      <TrustBadge score={data.score} level={data.level} />
      <span>{data.reasons.join(' · ')}</span>
    </div>
  )
}

// ---------------- Catalog ----------------
export function Catalog() {
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [onlyAvailable, setOnlyAvailable] = useState(false)
  const cats = useApi(() => api('/categories'))
  const params = new URLSearchParams()
  if (query) params.set('q', query)
  if (category) params.set('category_id', category)
  if (onlyAvailable) params.set('available', 'true')
  const books = useApi(() => api(`/books?${params}`), [query, category, onlyAvailable])
  const borrow = useBorrow()

  return (
    <>
      <PageHeader title="Catalog" intro="Click a cover to read about the book. Borrow is one click; it goes to the librarian first only if your trust score is below 70.">
      </PageHeader>
      <div className="mb-4"><TrustLine /></div>

      <form className="mb-6 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); setQuery(q.trim()) }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search title, author or topic"
          aria-label="Search books" className="min-w-60 flex-1 rounded-md border border-line bg-sheet px-3 py-2" />
        <label className="flex items-center gap-2 px-2 text-sm">
          <input type="checkbox" checked={onlyAvailable} onChange={(e) => setOnlyAvailable(e.target.checked)} /> On the shelf
        </label>
        <Button>Search</Button>
        {query && <Button type="button" variant="quiet" onClick={() => { setQ(''); setQuery('') }}>Clear</Button>}
      </form>

      {cats.data?.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2" role="group" aria-label="Filter by category">
          {[{ id: '', name: 'All categories', book_count: null }, ...cats.data].map((c) => {
            const on = String(category) === String(c.id)
            return (
              <button key={c.id || 'all'} type="button" aria-pressed={on} onClick={() => setCategory(c.id)}
                className={`flex items-center gap-2 rounded-full border py-1 pr-3 pl-1 text-sm transition ${on ? 'border-room bg-room text-white' : 'border-line bg-sheet text-ink hover:border-room'}`}>
                <span className={`relative h-6 w-6 overflow-hidden rounded-full ${c.id ? motifClass(c.name) : ''} ${on ? 'bg-room-deep' : 'bg-room'}`} aria-hidden="true" />
                {c.name}{c.book_count != null && <span className={on ? 'text-white/75' : 'text-ink-soft'}>{c.book_count}</span>}
              </button>
            )
          })}
        </div>
      )}

      <ErrorNote error={books.error} />
      {books.loading ? <Loading label="Fetching the shelves" /> : !books.data ? null : books.data?.length === 0 ? (
        <Empty>No books match “{query}”. Try a broader word, or ask on the For you page.</Empty>
      ) : (
        <div className="grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {books.data?.map((b) => <BookCard key={b.id} book={b} onBorrow={borrow} />)}
        </div>
      )}
    </>
  )
}

// ---------------- My books ----------------
export function MyBooks() {
  const loans = useApi(() => api('/loans/me'))
  const toast = useToast()
  const [busy, setBusy] = useState(null)

  const giveBack = async (loan) => {
    setBusy(loan.id)
    try {
      await api(`/loans/${loan.id}/return`, { method: 'POST' })
      toast(`Returned “${loan.book.title}”.`)
      loans.reload()
    } catch (e) { toast(e.message, 'error') } finally { setBusy(null) }
  }

  const current = loans.data?.filter((l) => l.status === 'borrowed') ?? []
  const pending = loans.data?.filter((l) => l.status === 'pending') ?? []
  const past = loans.data?.filter((l) => ['returned', 'rejected'].includes(l.status)) ?? []

  return (
    <>
      <PageHeader title="My books" intro="Books you have now, requests waiting for the librarian, and everything you've read." />
      <ErrorNote error={loans.error} />
      {loans.loading ? <Loading /> : !loans.data ? null : (
        <div className="flex flex-col gap-6">
          <Panel title={`On loan (${current.length})`}>
            {current.length === 0 ? <Empty>You have no books out. <Link to="/" className="font-semibold text-room">Browse the catalog</Link></Empty> : (
              <ul className="divide-y divide-line">
                {current.map((l) => (
                  <li key={l.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                    <div className="flex items-center gap-3">
                      <span className="h-12 w-8 rounded-sm" style={{ background: l.book.cover_color }} aria-hidden />
                      <div>
                        <div className="font-book font-semibold">{l.book.title}</div>
                        <div className={`text-sm ${l.days_overdue ? 'font-semibold text-stamp' : 'text-ink-soft'}`}>
                          {l.days_overdue ? `Overdue by ${l.days_overdue} day(s). A fine is added when it comes back.` : `Due ${fmtDate(l.due_at)}`}
                        </div>
                      </div>
                    </div>
                    <Button variant="quiet" disabled={busy === l.id} onClick={() => giveBack(l)}>
                      {busy === l.id ? 'Returning…' : 'Return book'}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          {pending.length > 0 && (
            <Panel title={`Waiting for approval (${pending.length})`}>
              <ul className="divide-y divide-line">
                {pending.map((l) => (
                  <li key={l.id} className="flex justify-between py-3">
                    <span className="font-book font-semibold">{l.book.title}</span>
                    <span className="text-sm text-ink-soft">Requested {fmtDateTime(l.requested_at)}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
          <Panel title="Reading history">
            {past.length === 0 ? <Empty>Books you return will be listed here.</Empty> : (
              <table className="w-full text-sm">
                <thead className="text-left text-ink-soft"><tr><th className="py-2">Book</th><th>Borrowed</th><th>Returned</th><th>Status</th></tr></thead>
                <tbody className="divide-y divide-line">
                  {past.map((l) => (
                    <tr key={l.id}>
                      <td className="py-2 font-medium">{l.book.title}</td>
                      <td>{fmtDate(l.borrowed_at)}</td><td>{fmtDate(l.returned_at)}</td>
                      <td><StatusPill status={l.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        </div>
      )}
    </>
  )
}

// ---------------- For you: recommendations + assistant ----------------
const SECTIONS = [
  ['close_in_meaning', 'Close in meaning to what you read'],
  ['similar', 'Similar themes or author'],
  ['same_topic', 'More on the same topic'],
  ['also_borrowed', 'Readers like you also borrowed'],
  ['different', 'Try something different'],
  ['popular', 'Popular with other readers'],
]

export function ForYou() {
  const recs = useApi(() => api('/recommendations/me'))
  const borrow = useBorrow()
  return (
    <>
      <PageHeader title="For you" intro="Picks based on the books you've borrowed. Each one says why it was suggested." />
      <Assistant onBorrow={borrow} />
      <ErrorNote error={recs.error} />
      {recs.loading ? <Loading label="Finding books for you" /> : !recs.data ? null : SECTIONS.map(([key, title]) =>
        recs.data?.[key]?.length ? (
          <section key={key} className="mt-10">
            <h2 className="mb-4 text-xl font-semibold">{title}</h2>
            <div className="grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {recs.data[key].map((r) => <BookCard key={r.book.id} book={r.book} reason={r.reason} onBorrow={borrow} />)}
            </div>
          </section>
        ) : null,
      )}
    </>
  )
}

export function Assistant({ onBorrow, title = 'Ask the library' }) {
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const ask = async (e) => {
    e.preventDefault()
    if (question.trim().length < 2) return
    setBusy(true); setError(null)
    try { setResult(await api('/assistant/ask', { method: 'POST', body: { question } })) }
    catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <Panel title={title}>
      <form onSubmit={ask} className="flex flex-wrap gap-2">
        <input value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={500}
          placeholder="e.g. a book about space survival, or something on good habits" aria-label="Question"
          className="min-w-60 flex-1 rounded-md border border-line px-3 py-2" />
        <Button disabled={busy}>{busy ? 'Searching…' : 'Ask'}</Button>
      </form>
      <ErrorNote error={error} />
      {result && <AssistantResult result={result} onBorrow={onBorrow} />}
    </Panel>
  )
}

const MODEL_NAMES = { 'anthropic/claude-haiku-4.5': 'Claude Haiku 4.5', none: 'catalog search (no AI)' }
const FOUND_BY = { semantic: 'meaning', keyword: 'words' }

function AssistantResult({ result, onBorrow }) {
  const recommended = result.books.filter((b) => result.recommended.includes(b.id))
  const others = result.books.filter((b) => !result.recommended.includes(b.id))
  const reason = (b) => `Matched by ${(result.found_by[b.id] || []).map((s) => FOUND_BY[s] || s).join(' + ')}`
  const grid = 'grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6'
  return (
    <div className="mt-4">
      <RichText text={result.answer} className="max-w-3xl leading-relaxed" />
      <p className="mt-2 text-xs text-ink-soft">
        Answered by {MODEL_NAMES[result.provider] || result.provider} · searched by {result.retrieval === 'hybrid' ? 'meaning and words' : 'words'}
      </p>
      {result.error && <p className="mt-2 text-xs text-[#7a5a17]">The AI service had a problem, so this answer uses catalog search only.</p>}
      {recommended.length > 0 && (
        <div className={`mt-4 ${grid}`}>
          {recommended.map((b) => <BookCard key={b.id} book={b} onBorrow={onBorrow} reason={reason(b)} />)}
        </div>
      )}
      {others.length > 0 && (
        <details className="mt-6" open={recommended.length === 0}>
          <summary className="cursor-pointer text-sm font-semibold text-room">Other matches ({others.length})</summary>
          <div className={`mt-4 ${grid}`}>
            {others.map((b) => <BookCard key={b.id} book={b} onBorrow={onBorrow} reason={reason(b)} />)}
          </div>
        </details>
      )}
    </div>
  )
}

// ---------------- Fines ----------------
export function MyFines() {
  const fines = useApi(() => api('/fines/me'))
  const unpaid = fines.data?.filter((f) => f.status === 'unpaid') ?? []
  const total = unpaid.reduce((s, f) => s + f.amount, 0)
  return (
    <>
      <PageHeader title="Fines" intro="A fine is added for each day a book comes back late. Pay at the library desk; the librarian marks it paid here." />
      <ErrorNote error={fines.error} />
      {fines.loading ? <Loading /> : !fines.data ? null : (
        <>
          <p className={`mb-4 font-book text-2xl font-semibold ${total ? 'text-stamp' : 'text-room'}`}>
            {total ? `Rs ${total} unpaid` : 'Nothing to pay'}
          </p>
          {fines.data.length === 0 ? <Empty>No fines. Every book came back on time.</Empty> : (
            <Panel>
              <table className="w-full text-sm">
                <thead className="text-left text-ink-soft"><tr><th className="py-2">Book</th><th>Days late</th><th>Amount</th><th>Status</th><th>Settled</th></tr></thead>
                <tbody className="divide-y divide-line">
                  {fines.data.map((f) => (
                    <tr key={f.id}>
                      <td className="py-2 font-medium">{f.book_title}</td><td className="tabular-nums">{f.days_late}</td>
                      <td className="tabular-nums">Rs {f.amount}</td><td><StatusPill status={f.status} /></td><td>{fmtDate(f.paid_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          )}
        </>
      )}
    </>
  )
}

// ---------------- History (sessions + activity) ----------------
const ACTION_TEXT = {
  'auth.login': 'Logged in', 'auth.logout': 'Logged out', 'loan.borrowed': 'Borrowed a book',
  'loan.pending': 'Requested a book', 'loan.returned': 'Returned a book', 'assistant.ask': 'Asked the library',
  'user.registered': 'Created account', 'loan.seeded': 'Past loan (imported)',
}

export function History() {
  const sessions = useApi(() => api('/auth/me/sessions'))
  const activity = useApi(() => api('/activity/me'))
  return (
    <>
      <PageHeader title="History" intro="Every login, logout and library action is saved, so it's still here the next time you open the app." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Logins">
          <ErrorNote error={sessions.error} />
          {sessions.loading ? <Loading /> : !sessions.data ? null : (
            <table className="w-full text-sm">
              <thead className="text-left text-ink-soft"><tr><th className="py-2">Logged in</th><th>Logged out</th></tr></thead>
              <tbody className="divide-y divide-line">
                {sessions.data?.map((s) => (
                  <tr key={s.id}><td className="py-2">{fmtDateTime(s.login_at)}</td>
                    <td>{s.logout_at ? fmtDateTime(s.logout_at) : <span className="text-room">Active or closed without logout</span>}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
        <Panel title="Activity">
          <ErrorNote error={activity.error} />
          {activity.loading ? <Loading /> : !activity.data ? null : (
            <ul className="divide-y divide-line text-sm">
              {activity.data?.map((a) => (
                <li key={a.id} className="flex justify-between gap-4 py-2">
                  <span>{ACTION_TEXT[a.action] || a.action}{a.details?.question ? `: “${a.details.question}”` : ''}{a.details?.title ? `: ${a.details.title}` : ''}</span>
                  <span className="whitespace-nowrap text-ink-soft">{fmtDateTime(a.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </>
  )
}
