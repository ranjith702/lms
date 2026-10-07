import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, setUnauthorizedHandler, tokenStore } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [previousSession, setPreviousSession] = useState(null)
  const [loading, setLoading] = useState(true)

  const clear = useCallback(() => { tokenStore.clear(); setUser(null) }, [])

  useEffect(() => {
    setUnauthorizedHandler(clear)
    if (!tokenStore.get()) { setLoading(false); return }
    // Re-opening the app: the token is still valid, so restore the user from the server.
    api('/auth/me').then(setUser).catch(clear).finally(() => setLoading(false))
  }, [clear])

  const login = async (email, password) => {
    const data = await api('/auth/login', { method: 'POST', body: { email, password } })
    tokenStore.set(data.access_token)
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
