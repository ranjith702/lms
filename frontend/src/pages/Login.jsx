import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import Shelf from '../components/Shelf'
import { BrandMark, Button, ErrorNote, useApi } from '../components/ui'
import { useAuth } from '../context/AuthContext'

const DEMO = [
  ['librarian@library.dev', 'Librarian@123', 'Librarian'],
  ['asha@library.dev', 'Student@123', 'Asha · reliable reader'],
  ['ravi@library.dev', 'Student@123', 'Ravi · late returns'],
  ['meera@library.dev', 'Student@123', 'Meera · overdue book'],
  ['kiran@library.dev', 'Student@123', 'Kiran · new student'],
]

function Shell({ title, children }) {
  const shelf = useApi(() => api('/public/shelf'))
  return (
    <div className="grid min-h-screen md:grid-cols-2">
      <div className="hidden flex-col justify-between gap-10 border-r border-line bg-room-soft/60 p-12 md:flex">
        <p className="font-book text-4xl leading-tight font-semibold text-room-deep">Borrow a book in one click.<br />Bring it back on time,<br />and it stays that way.</p>
        {shelf.data?.books?.length > 0 && <Shelf books={shelf.data.books} compact />}
        <p className="max-w-md text-ink-soft">Students with a good return record borrow instantly. Late returns and unpaid fines send requests to the librarian first.</p>
      </div>
      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <Link to="/" className="flex items-center gap-2 font-book text-xl font-semibold text-room-deep"><BrandMark />Reading Room</Link>
          <h1 className="mt-6 text-2xl font-semibold">{title}</h1>
          {children}
        </div>
      </div>
    </div>
  )
}

export function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try { await login(email, password); navigate('/') } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <Shell title="Log in">
      <form onSubmit={submit} className="mt-6 flex flex-col gap-4">
        <label className="text-sm font-medium">Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email"
            className="mt-1 w-full rounded-md border border-line bg-sheet px-3 py-2" />
        </label>
        <label className="text-sm font-medium">Password
          <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password"
            className="mt-1 w-full rounded-md border border-line bg-sheet px-3 py-2" />
        </label>
        <ErrorNote error={error} />
        <Button disabled={busy}>{busy ? 'Logging in…' : 'Log in'}</Button>
      </form>
      <p className="mt-4 text-sm text-ink-soft">New student? <Link to="/register" className="font-semibold text-room hover:underline">Create an account</Link></p>

      <div className="mt-8 border-t border-line pt-4">
        <p className="text-sm font-medium">Demo accounts</p>
        <div className="mt-2 flex flex-col gap-1">
          {DEMO.map(([e, p, label]) => (
            <button key={e} type="button" onClick={() => { setEmail(e); setPassword(p) }}
              className="rounded-md px-2 py-1 text-left text-sm text-ink-soft hover:bg-room-soft hover:text-room-deep">
              {label}
            </button>
          ))}
        </div>
      </div>
    </Shell>
  )
}

export function Register() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      await api('/auth/register', { method: 'POST', body: form })
      await login(form.email, form.password)
      navigate('/')
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <Shell title="Create a student account">
      <form onSubmit={submit} className="mt-6 flex flex-col gap-4">
        <label className="text-sm font-medium">Full name
          <input required minLength={2} value={form.name} onChange={set('name')} className="mt-1 w-full rounded-md border border-line bg-sheet px-3 py-2" />
        </label>
        <label className="text-sm font-medium">Email
          <input type="email" required value={form.email} onChange={set('email')} className="mt-1 w-full rounded-md border border-line bg-sheet px-3 py-2" />
        </label>
        <label className="text-sm font-medium">Password (8+ characters)
          <input type="password" required minLength={8} value={form.password} onChange={set('password')} autoComplete="new-password"
            className="mt-1 w-full rounded-md border border-line bg-sheet px-3 py-2" />
        </label>
        <ErrorNote error={error} />
        <Button disabled={busy}>{busy ? 'Creating account…' : 'Create account'}</Button>
      </form>
      <p className="mt-4 text-sm text-ink-soft">Already registered? <Link to="/login" className="font-semibold text-room hover:underline">Log in</Link></p>
    </Shell>
  )
}
