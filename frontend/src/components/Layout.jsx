import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { fmtDateTime } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { BrandMark } from './ui'

const STUDENT_NAV = [
  ['/', 'Catalog'], ['/my-books', 'My books'], ['/for-you', 'For you'], ['/fines', 'Fines'], ['/history', 'History'],
]
const LIBRARIAN_NAV = [
  ['/', 'Desk'], ['/requests', 'Requests'], ['/loans', 'Loans'], ['/fines', 'Fines'], ['/students', 'Students'],
  ['/books', 'Books'], ['/assistant', 'Ask the catalog'], ['/activity', 'Activity log'],
]

export default function Layout() {
  const { user, logout, previousSession, setPreviousSession } = useAuth()
  const navigate = useNavigate()
  const nav = user.role === 'librarian' ? LIBRARIAN_NAV : STUDENT_NAV

  const doLogout = async () => { await logout(); navigate('/login') }

  return (
    <div className="min-h-screen md:grid md:grid-cols-[230px_1fr]">
      <aside className="flex flex-col border-b border-line bg-sheet md:sticky md:top-0 md:h-screen md:overflow-y-auto md:border-r md:border-b-0">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <BrandMark className="h-7 w-7" />
          <div>
            <div className="font-book text-xl leading-tight font-semibold text-room-deep">Reading Room</div>
            <div className="text-sm text-ink-soft">{user.role === 'librarian' ? 'Librarian desk' : 'Student library'}</div>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0" aria-label="Main">
          {nav.map(([to, label]) => (
            <NavLink
              key={to} to={to} end={to === '/'}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-md border-l-[3px] px-3 py-2 text-sm font-medium transition ${isActive ? 'border-brass bg-room-soft text-room-deep' : 'border-transparent text-ink-soft hover:bg-paper hover:text-ink'}`}
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto border-t border-line px-5 py-4 text-sm">
          <div className="font-semibold">{user.name}</div>
          <div className="truncate text-ink-soft">{user.email}</div>
          <button onClick={doLogout} className="mt-3 rounded-md border border-line px-3 py-1.5 text-xs font-semibold text-room hover:border-room">
            Log out
          </button>
        </div>
      </aside>

      <main className="mx-auto w-full max-w-6xl px-4 py-6 md:px-8 md:py-8">
        {previousSession && (
          <div className="mb-6 flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-sheet px-4 py-2.5 text-sm text-ink-soft">
            <span>
              Welcome back. Your last visit started {fmtDateTime(previousSession.login_at)}
              {previousSession.logout_at ? ` and you logged out ${fmtDateTime(previousSession.logout_at)}.` : ' (that session was not logged out).'}
            </span>
            <button className="text-xs font-semibold text-room hover:underline" onClick={() => setPreviousSession(null)}>Dismiss</button>
          </div>
        )}
        <Outlet />
      </main>
    </div>
  )
}
