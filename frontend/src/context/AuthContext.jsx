import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, setUnauthorizedHandler } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [previousSession, setPreviousSession] = useState(null)
  // JavaScript can't see the httpOnly cookie, so on every app start we ask the server who we are.
  const [loading, setLoading] = useState(true)

  const clear = useCallback(() => setUser(null), [])

  useEffect(() => {
    setUnauthorizedHandler(clear)
    // 200 = the cookie still holds a live session; 401 = logged out (show Landing).
    api('/auth/me').then(setUser).catch(clear).finally(() => setLoading(false))
  }, [clear])

  const login = async (email, password) => {
    const data = await api('/auth/login', { method: 'POST', body: { email, password } })
    setPreviousSession(data.previous_session)
    setUser(data.user)
    return data.user
  }

  const logout = async () => {
    try { await api('/auth/logout', { method: 'POST' }) } finally { clear() }
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, previousSession, setPreviousSession }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
