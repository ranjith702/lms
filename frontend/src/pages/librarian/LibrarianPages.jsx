import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, fmtDate, fmtDateTime } from '../../api/client'
import BookCard from '../../components/BookCard'
import RichText from '../../components/RichText'
import {
  Button, Empty, ErrorNote, Loading, PageHeader, Panel, Stat, StatusPill, TrustBadge, useApi, useToast,
} from '../../components/ui'
import { Assistant } from '../student/StudentPages'

function useAction() {
  const toast = useToast()
  const [busy, setBusy] = useState(null)
  const run = async (key, fn, okMessage, after) => {
    setBusy(key)
    try { await fn(); toast(okMessage); after?.() } catch (e) { toast(e.message, 'error') } finally { setBusy(null) }
  }
  return [busy, run]
}

// ---------------- Desk (dashboard) ----------------
export function Desk() {
  const dash = useApi(() => api('/dashboard'))
  const d = dash.data
  return (
    <>
      <PageHeader title="Librarian desk" intro="What needs attention today." />
      <ErrorNote error={dash.error} />
      {dash.loading ? <Loading /> : !dash.data ? null : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
            <Stat label="Titles in catalog" value={d.books} />
            <Stat label="Copies on loan" value={d.copies_out} tone="room" />
            <Link to="/requests"><Stat label="Requests waiting" value={d.pending} tone={d.pending ? 'brass' : 'ink'} /></Link>
            <Link to="/loans?status=overdue"><Stat label="Overdue loans" value={d.overdue} tone={d.overdue ? 'stamp' : 'ink'} /></Link>
            <Link to="/fines"><Stat label="Unpaid fines (Rs)" value={d.unpaid_fines_total} tone={d.unpaid_fines_total ? 'stamp' : 'ink'} /></Link>
            <Stat label="Students" value={d.students} />
          </div>
          <Panel title="Students who need a look" className="mt-6">
            {d.at_risk.length === 0 ? <Empty>Every student is in good standing.</Empty> : (
              <ul className="divide-y divide-line">
                {d.at_risk.map((s) => (
                  <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                    <div>
                      <Link to={`/students/${s.id}`} className="font-semibold text-room hover:underline">{s.name}</Link>
                      <div className="text-sm text-ink-soft">{s.reasons.join(' · ')}</div>
                    </div>
                    <TrustBadge score={s.score} level={s.level} />
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </>
      )}
    </>
  )
}

// ---------------- Requests (approval queue) ----------------
export function Requests() {
  const pending = useApi(() => api('/loans?status=pending'))
  const students = useApi(() => api('/users/students'))
  const [busy, run] = useAction()
  const trustOf = (id) => students.data?.find((s) => s.id === id)

  return (
    <>
      <PageHeader title="Requests" intro="Students below trust 70 need your approval. The copy is already set aside for them; rejecting puts it back on the shelf." />
      <ErrorNote error={pending.error} />
      {pending.loading ? <Loading /> : !pending.data ? null : pending.data.length === 0 ? <Empty>No requests waiting.</Empty> : (
        <Panel>
          <ul className="divide-y divide-line">
            {pending.data.map((l) => {
              const t = trustOf(l.user_id)
              return (
                <li key={l.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div>
                    <div className="font-book font-semibold">{l.book.title}</div>
                    <div className="text-sm text-ink-soft">
                      <Link to={`/students/${l.user_id}`} className="font-medium text-room hover:underline">{l.student_name}</Link>
                      {' '}asked {fmtDateTime(l.requested_at)}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {t && <TrustBadge score={t.score} level={t.level} compact />}
                    <Button disabled={busy === l.id} onClick={() => run(l.id, () => api(`/loans/${l.id}/approve`, { method: 'POST' }), `Approved for ${l.student_name}.`, pending.reload)}>Approve</Button>
                    <Button variant="quiet" disabled={busy === l.id} onClick={() => run(l.id, () => api(`/loans/${l.id}/reject`, { method: 'POST' }), 'Request rejected; copy is back on the shelf.', pending.reload)}>Reject</Button>
                  </div>
                </li>
              )
            })}
          </ul>
        </Panel>
      )}
    </>
  )
}

// ---------------- Loans ----------------
const LOAN_TABS = [['borrowed', 'On loan'], ['overdue', 'Overdue'], ['pending', 'Pending'], ['returned', 'Returned'], ['', 'All']]

export function Loans() {
  const initial = new URLSearchParams(window.location.search).get('status') ?? 'borrowed'
  const [tab, setTab] = useState(initial)
  const loans = useApi(() => api(`/loans${tab ? `?status=${tab}` : ''}`), [tab])
  const [busy, run] = useAction()
  return (
    <>
      <PageHeader title="Loans" intro="Mark books returned when students hand them in at the desk. Late returns create a fine automatically." />
      <div className="mb-4 flex flex-wrap gap-1" role="tablist">
        {LOAN_TABS.map(([value, label]) => (
          <button key={label} role="tab" aria-selected={tab === value} onClick={() => setTab(value)}
            className={`rounded-md px-3 py-1.5 text-sm font-semibold ${tab === value ? 'bg-room text-white' : 'bg-sheet text-ink-soft border border-line'}`}>{label}</button>
        ))}
      </div>
      <ErrorNote error={loans.error} />
      {loans.loading ? <Loading /> : !loans.data ? null : loans.data.length === 0 ? <Empty>Nothing here.</Empty> : (
        <Panel>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-ink-soft"><tr><th className="py-2">Book</th><th>Student</th><th>Borrowed</th><th>Due</th><th>Status</th><th /></tr></thead>
              <tbody className="divide-y divide-line">
                {loans.data.map((l) => (
                  <tr key={l.id}>
                    <td className="py-2 font-medium">{l.book.title}</td>
                    <td><Link className="text-room hover:underline" to={`/students/${l.user_id}`}>{l.student_name}</Link></td>
                    <td>{fmtDate(l.borrowed_at)}</td><td>{fmtDate(l.due_at)}</td>
                    <td><StatusPill status={l.status} overdue={l.days_overdue} /></td>
                    <td className="text-right">
                      {l.status === 'borrowed' && (
                        <Button variant="quiet" className="py-1" disabled={busy === l.id}
                          onClick={() => run(l.id, () => api(`/loans/${l.id}/return`, { method: 'POST' }),
                            l.days_overdue ? `Returned ${l.days_overdue} day(s) late; fine added.` : 'Marked returned.', loans.reload)}>
                          Mark returned
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </>
  )
}

// ---------------- Fines ----------------
export function Fines() {
  const [status, setStatus] = useState('unpaid')
  const fines = useApi(() => api(`/fines${status ? `?status=${status}` : ''}`), [status])
  const [busy, run] = useAction()
  return (
    <>
      <PageHeader title="Fines" intro="Mark a fine paid when the student pays at the desk, or waive it. Unpaid fines lower a student's trust score.">
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Fine status" className="rounded-md border border-line bg-sheet px-3 py-2">
          <option value="unpaid">Unpaid</option><option value="paid">Paid</option><option value="waived">Waived</option><option value="">All</option>
        </select>
      </PageHeader>
      <ErrorNote error={fines.error} />
      {fines.loading ? <Loading /> : !fines.data ? null : fines.data.length === 0 ? <Empty>No {status} fines.</Empty> : (
        <Panel>
          <table className="w-full text-sm">
            <thead className="text-left text-ink-soft"><tr><th className="py-2">Student</th><th>Book</th><th>Days late</th><th>Amount</th><th>Status</th><th /></tr></thead>
            <tbody className="divide-y divide-line">
              {fines.data.map((f) => (
                <tr key={f.id}>
                  <td className="py-2"><Link className="text-room hover:underline" to={`/students/${f.user_id}`}>{f.student_name}</Link></td>
                  <td>{f.book_title}</td><td className="tabular-nums">{f.days_late}</td><td className="tabular-nums">Rs {f.amount}</td>
                  <td><StatusPill status={f.status} /></td>
                  <td className="flex justify-end gap-2 py-2">
                    {f.status === 'unpaid' && (<>
                      <Button className="py-1" disabled={busy === f.id} onClick={() => run(f.id, () => api(`/fines/${f.id}/pay`, { method: 'POST' }), `Rs ${f.amount} marked paid.`, fines.reload)}>Mark paid</Button>
                      <Button variant="quiet" className="py-1" disabled={busy === f.id} onClick={() => run(f.id, () => api(`/fines/${f.id}/waive`, { method: 'POST' }), 'Fine waived.', fines.reload)}>Waive</Button>
                    </>)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </>
  )
}

// ---------------- Students + profile (librarian assistant) ----------------
export function Students() {
  const students = useApi(() => api('/users/students'))
  return (
    <>
      <PageHeader title="Students" intro="Open a student to see their record and what to suggest next." />
      <ErrorNote error={students.error} />
      {students.loading ? <Loading /> : !students.data ? null : (
        <Panel>
          <table className="w-full text-sm">
            <thead className="text-left text-ink-soft"><tr><th className="py-2">Name</th><th>Email</th><th>Books out</th><th>Unpaid</th><th>Trust</th></tr></thead>
            <tbody className="divide-y divide-line">
              {students.data.map((s) => (
                <tr key={s.id}>
                  <td className="py-2"><Link className="font-semibold text-room hover:underline" to={`/students/${s.id}`}>{s.name}</Link></td>
                  <td className="text-ink-soft">{s.email}</td><td className="tabular-nums">{s.active_loans}</td>
                  <td className="tabular-nums">{s.unpaid_amount ? `Rs ${s.unpaid_amount}` : '—'}</td>
                  <td><TrustBadge score={s.score} level={s.level} compact /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </>
  )
}

export function StudentProfile() {
  const { id } = useParams()
  const ins = useApi(() => api(`/users/${id}/insights`), [id])
  if (ins.loading) return <Loading />
  if (ins.error) return <ErrorNote error={ins.error} />
  const d = ins.data
  return (
    <>
      <PageHeader title={d.student.name} intro={`${d.student.email} · member since ${fmtDate(d.student.created_at)}`}>
        <TrustBadge score={d.trust.score} level={d.trust.level} />
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <Panel title="What to do next">
          <ul className="flex flex-col gap-2">
            {d.suggestions.map((s) => <li key={s} className="rounded-md bg-room-soft px-3 py-2 text-room-deep">{s}</li>)}
          </ul>
          <p className="mt-4 text-sm text-ink-soft">Why the trust score is {d.trust.score}: {d.trust.reasons.join('; ')}.</p>
          <AiBrief studentId={d.student.id} />
        </Panel>
        <Panel title="Reading profile">
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div><dt className="text-ink-soft">On-time returns</dt><dd className="font-book text-2xl font-semibold">{d.on_time_rate === null ? '—' : `${d.on_time_rate}%`}</dd></div>
            <div><dt className="text-ink-soft">Unpaid fines</dt><dd className={`font-book text-2xl font-semibold ${d.trust.unpaid_amount ? 'text-stamp' : ''}`}>Rs {d.trust.unpaid_amount}</dd></div>
            <div className="col-span-2"><dt className="text-ink-soft">Favourite topics</dt>
              <dd className="mt-1">{d.favorite_categories.length ? d.favorite_categories.map((c) => `${c.name} (${c.count})`).join(', ') : 'No reading yet'}</dd></div>
          </dl>
        </Panel>
      </div>

      {d.suggest_next.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-4 text-xl font-semibold">Books to suggest to {d.student.name.split(' ')[0]}</h2>
          <div className="grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3 lg:grid-cols-5">
            {d.suggest_next.map((r) => <BookCard key={r.book.id} book={r.book} reason={r.reason} />)}
          </div>
        </section>
      )}

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <Panel title="Loans">
          {d.loans.length === 0 ? <Empty>No loans yet.</Empty> : (
            <ul className="divide-y divide-line text-sm">
              {d.loans.map((l) => (
                <li key={l.id} className="flex items-center justify-between gap-3 py-2">
                  <span><span className="font-medium">{l.book.title}</span> <span className="text-ink-soft">· due {fmtDate(l.due_at)}</span></span>
                  <StatusPill status={l.status} overdue={l.days_overdue} />
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel title="Recent logins">
          <ul className="divide-y divide-line text-sm">
            {d.sessions.map((s) => (
              <li key={s.id} className="flex justify-between py-2"><span>{fmtDateTime(s.login_at)}</span>
                <span className="text-ink-soft">{s.logout_at ? `out ${fmtDateTime(s.logout_at)}` : 'no logout recorded'}</span></li>
            ))}
            {d.sessions.length === 0 && <li className="py-2 text-ink-soft">Never logged in.</li>}
          </ul>
        </Panel>
      </div>
    </>
  )
}

function AiBrief({ studentId }) {
  const [state, setState] = useState({ busy: false, brief: null, model: null, error: null })
  const write = async () => {
    setState({ busy: true, brief: null, model: null, error: null })
    try {
      const r = await api(`/users/${studentId}/ai-brief`, { method: 'POST' })
      setState({ busy: false, brief: r.brief, model: r.model, error: null })
    } catch (e) { setState({ busy: false, brief: null, model: null, error: e.message }) }
  }
  return (
    <div className="mt-4 border-t border-line pt-4">
      <Button variant="brass" onClick={write} disabled={state.busy}>
        {state.busy ? 'Writing brief…' : state.brief ? 'Write a new brief' : 'Write an AI brief'}
      </Button>
      <p className="mt-1 text-xs text-ink-soft">Sends this student's record to the AI without their name or email.</p>
      <ErrorNote error={state.error} />
      {state.brief && (
        <div className="mt-3 rounded-md bg-brass-soft px-3 py-2 text-sm leading-relaxed">
          <RichText text={state.brief} />
          <p className="mt-2 text-xs text-ink-soft">Written by {state.model}. Check it against the record above.</p>
        </div>
      )}
    </div>
  )
}

// ---------------- Books (CRUD) ----------------
const EMPTY_BOOK = { title: '', author: '', isbn: '', category_id: '', description: '', tags: '', total_copies: 1, cover_color: '#1f4d3a' }

export function Books() {
  const books = useApi(() => api('/books'))
  const cats = useApi(() => api('/categories'))
  const toast = useToast()
  const [form, setForm] = useState(null) // null = closed; {id?: ...} = editing
  const [error, setError] = useState(null)
  const [newCat, setNewCat] = useState('')

  const open = (b) => setForm(b ? { ...b, tags: b.tags.join(', '), isbn: b.isbn ?? '' } : { ...EMPTY_BOOK, category_id: cats.data?.[0]?.id ?? '' })
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const save = async (e) => {
    e.preventDefault()
    setError(null)
    const body = { ...form, isbn: form.isbn || null, category_id: Number(form.category_id), total_copies: Number(form.total_copies),
      tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean) }
    try {
      await api(form.id ? `/books/${form.id}` : '/books', { method: form.id ? 'PUT' : 'POST', body })
      toast(form.id ? 'Book updated.' : 'Book added to the catalog.')
      setForm(null); books.reload(); cats.reload()
    } catch (err) { setError(err.message) }
  }

  const remove = async (b) => {
    if (!window.confirm(`Delete “${b.title}”? This cannot be undone.`)) return
    try { await api(`/books/${b.id}`, { method: 'DELETE' }); toast('Book deleted.'); books.reload() }
    catch (err) { toast(err.message, 'error') }
  }

  const addCategory = async (e) => {
    e.preventDefault()
    try { await api('/categories', { method: 'POST', body: { name: newCat } }); toast(`Category “${newCat}” added.`); setNewCat(''); cats.reload() }
    catch (err) { toast(err.message, 'error') }
  }

  const renameCategory = async (c) => {
    const name = window.prompt(`Rename category “${c.name}” to:`, c.name)?.trim()
    if (!name || name === c.name) return
    try {
      await api(`/categories/${c.id}`, { method: 'PUT', body: { name, description: c.description } })
      toast(`Category renamed to “${name}”.`); cats.reload(); books.reload()
    } catch (err) { toast(err.message, 'error') }
  }

  const removeCategory = async (c) => {
    if (!window.confirm(`Delete category “${c.name}”?`)) return
    try { await api(`/categories/${c.id}`, { method: 'DELETE' }); toast('Category deleted.'); cats.reload() }
    catch (err) { toast(err.message, 'error') }
  }

  return (
    <>
      <PageHeader title="Books" intro="Add, edit or remove titles. Books with loan history can't be deleted, so records stay intact.">
        <Button onClick={() => open(null)}>Add book</Button>
      </PageHeader>

      {form && (
        <Panel title={form.id ? `Edit “${form.title}”` : 'Add a book'} className="mb-6">
          <form onSubmit={save} className="grid gap-3 md:grid-cols-2">
            {[['title', 'Title'], ['author', 'Author'], ['isbn', 'ISBN (optional)']].map(([k, label]) => (
              <label key={k} className="text-sm font-medium">{label}
                <input value={form[k]} onChange={set(k)} required={k !== 'isbn'} className="mt-1 w-full rounded-md border border-line px-3 py-2" />
              </label>
            ))}
            <label className="text-sm font-medium">Category
              <select value={form.category_id} onChange={set('category_id')} required className="mt-1 w-full rounded-md border border-line px-3 py-2">
                {cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium">Copies owned
              <input type="number" min={1} max={100} value={form.total_copies} onChange={set('total_copies')} className="mt-1 w-full rounded-md border border-line px-3 py-2" />
            </label>
            <label className="text-sm font-medium">Cover colour
              <input type="color" value={form.cover_color} onChange={set('cover_color')} className="mt-1 h-10 w-full rounded-md border border-line" />
            </label>
            <label className="text-sm font-medium md:col-span-2">Topics (comma separated)
              <input value={form.tags} onChange={set('tags')} placeholder="space, survival" className="mt-1 w-full rounded-md border border-line px-3 py-2" />
            </label>
            <label className="text-sm font-medium md:col-span-2">Description
              <textarea value={form.description} onChange={set('description')} rows={3} className="mt-1 w-full rounded-md border border-line px-3 py-2" />
            </label>
            <div className="md:col-span-2"><ErrorNote error={error} /></div>
            <div className="flex gap-2 md:col-span-2">
              <Button>{form.id ? 'Save changes' : 'Add book'}</Button>
              <Button type="button" variant="quiet" onClick={() => setForm(null)}>Cancel</Button>
            </div>
          </form>
        </Panel>
      )}

      <form onSubmit={addCategory} className="mb-4 flex flex-wrap items-center gap-2">
        <input value={newCat} onChange={(e) => setNewCat(e.target.value)} minLength={2} required placeholder="New category name"
          aria-label="New category" className="rounded-md border border-line bg-sheet px-3 py-2" />
        <Button variant="quiet">Add category</Button>
      </form>

      {cats.data?.length > 0 && (
        <ul aria-label="Categories" className="mb-6 flex flex-wrap gap-2">
          {cats.data.map((c) => (
            <li key={c.id} className="flex items-center gap-1 rounded-full border border-line bg-sheet py-1 pl-3 pr-1 text-sm">
              <span>{c.name} <span className="tabular-nums text-ink-soft">({c.book_count})</span></span>
              <button type="button" onClick={() => renameCategory(c)} aria-label={`Rename ${c.name}`}
                className="rounded-full px-2 text-ink-soft hover:bg-line">Rename</button>
              <button type="button" onClick={() => removeCategory(c)} aria-label={`Delete ${c.name}`}
                disabled={c.book_count > 0} title={c.book_count > 0 ? 'Move or delete its books first' : undefined}
                className="rounded-full px-2 text-stamp hover:bg-line disabled:cursor-not-allowed disabled:opacity-40">Delete</button>
            </li>
          ))}
        </ul>
      )}

      <ErrorNote error={books.error} />
      {books.loading ? <Loading /> : !books.data ? null : (
        <Panel>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-ink-soft"><tr><th className="py-2">Title</th><th>Author</th><th>Category</th><th>On shelf</th><th /></tr></thead>
              <tbody className="divide-y divide-line">
                {books.data.map((b) => (
                  <tr key={b.id}>
                    <td className="py-2 font-medium"><span className="mr-2 inline-block h-4 w-3 rounded-sm align-middle" style={{ background: b.cover_color }} />{b.title}</td>
                    <td>{b.author}</td><td>{b.category_name}</td><td className="tabular-nums">{b.available_copies}/{b.total_copies}</td>
                    <td className="flex justify-end gap-2 py-2">
                      <Button variant="quiet" className="py-1" onClick={() => open(b)}>Edit</Button>
                      <Button variant="quiet" className="py-1 text-stamp" onClick={() => remove(b)}>Delete</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </>
  )
}

// ---------------- Assistant + activity ----------------
export function LibrarianAssistant() {
  return (
    <>
      <PageHeader title="Ask the catalog" intro="Find books by topic or idea, e.g. when a student asks for something specific. For a student's record and what to suggest them, open their profile under Students." />
      <Assistant title="Search by idea" />
    </>
  )
}

export function Activity() {
  const feed = useApi(() => api('/activity?limit=200'))
  return (
    <>
      <PageHeader title="Activity log" intro="Every login, loan, return, fine and catalog change, newest first. Nothing is ever deleted." />
      <ErrorNote error={feed.error} />
      {feed.loading ? <Loading /> : !feed.data ? null : (
        <Panel>
          <table className="w-full text-sm">
            <thead className="text-left text-ink-soft"><tr><th className="py-2">When</th><th>Who</th><th>What</th><th>Details</th></tr></thead>
            <tbody className="divide-y divide-line">
              {feed.data.map((a) => (
                <tr key={a.id}>
                  <td className="whitespace-nowrap py-2 text-ink-soft">{fmtDateTime(a.created_at)}</td>
                  <td>{a.user_name ?? 'system'}</td><td className="font-medium">{a.action}</td>
                  <td className="text-ink-soft">{Object.entries(a.details || {}).map(([k, v]) => `${k}: ${v}`).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </>
  )
}
