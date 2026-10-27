import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { Loading } from './components/ui'
import { useAuth } from './context/AuthContext'
import Landing from './pages/Landing'
import * as L from './pages/librarian/LibrarianPages'
import { Login, Register } from './pages/Login'
import * as S from './pages/student/StudentPages'

export default function App() {
  const { user, loading } = useAuth()
  if (loading) return <Loading label="Opening the library" />

  if (!user) {
    return (
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    )
  }

  // Role decides which pages exist at all; the API enforces it again server-side.
  const pages = user.role === 'librarian'
    ? [['/', L.Desk], ['/requests', L.Requests], ['/loans', L.Loans], ['/fines', L.Fines],
      ['/students', L.Students], ['/students/:id', L.StudentProfile], ['/books', L.Books],
      ['/assistant', L.LibrarianAssistant], ['/activity', L.Activity]]
    : [['/', S.Catalog], ['/my-books', S.MyBooks], ['/for-you', S.ForYou], ['/fines', S.MyFines],
      ['/history', S.History]]

  return (
    <Routes>
      <Route element={<Layout />}>
        {pages.map(([path, Page]) => <Route key={path} path={path} element={<Page />} />)}
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
