import { Component } from 'react'

/** Last line of defence: a render crash shows a recovery screen instead of a blank app. */
export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('UI crashed:', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <div className="max-w-md">
          <h1 className="text-2xl font-semibold text-room-deep">This page hit a problem</h1>
          <p className="mt-2 text-ink-soft">Your data is safe. Reload to try again; if it keeps happening, log out and back in.</p>
          <button onClick={() => window.location.assign('/')}
            className="mt-4 rounded-md bg-room px-4 py-2 text-sm font-semibold text-white hover:bg-room-deep">
            Reload the library
          </button>
        </div>
      </div>
    )
  }
}
