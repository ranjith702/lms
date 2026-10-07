import { useState } from 'react'
import { fmtDate } from '../api/client'

/**
 * A book on the shelf. Click the cover to flip it and read the description.
 * `onBorrow` returns the borrow result; if the book was issued, a DUE stamp lands on the cover.
 */
export default function BookCard({ book, onBorrow, reason, disabled }) {
  const [flipped, setFlipped] = useState(false)
  const [busy, setBusy] = useState(false)
  const [stamp, setStamp] = useState(null) // { kind: 'due'|'pending', date }

  const out = book.available_copies === 0

  const borrow = async (e) => {
    e.stopPropagation()
    setBusy(true)
    try {
      const res = await onBorrow(book)
      if (res) {
        setFlipped(false)
        setStamp(res.loan.status === 'borrowed' ? { kind: 'due', date: res.loan.due_at } : { kind: 'pending' })
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="flex flex-col gap-2">
      <div
        className={`book h-64 cursor-pointer ${flipped ? 'flipped' : ''}`}
        onClick={() => setFlipped((f) => !f)}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), setFlipped((f) => !f))}
        role="button"
        tabIndex={0}
        aria-pressed={flipped}
        aria-label={`${book.title} by ${book.author}. ${flipped ? 'Showing description' : 'Press to read description'}`}
      >
        <div className="book-inner">
          <div className="book-face book-front flex flex-col justify-between p-4 pl-6 text-white" style={{ background: book.cover_color }}>
            <div>
              <h3 className="font-book text-lg font-semibold leading-snug">{book.title}</h3>
              <p className="mt-2 text-sm text-white/80">{book.author}</p>
            </div>
            <p className="text-xs text-white/70">{book.category_name}</p>
            {stamp && (
              <div className="stamp">
                {stamp.kind === 'due' ? (<><div className="text-sm">DUE</div><div className="text-base">{fmtDate(stamp.date)}</div></>)
                  : <div className="text-sm">REQUESTED</div>}
              </div>
            )}
          </div>
          <div className="book-face book-back flex flex-col border border-line bg-sheet p-4">
            <h3 className="font-book text-base font-semibold leading-snug">{book.title}</h3>
            <p className="mt-2 flex-1 overflow-y-auto text-sm leading-relaxed text-ink-soft">{book.description}</p>
            {book.tags?.length > 0 && (
              <p className="mt-2 text-xs text-ink-soft">{book.tags.join(', ')}</p>
            )}
          </div>
        </div>
      </div>

      {reason && <p className="text-xs leading-snug text-ink-soft">{reason}</p>}

      <div className="flex items-center justify-between gap-2">
        <span className={`text-xs font-medium ${out ? 'text-stamp' : 'text-ink-soft'}`}>
          {out ? 'All copies out' : `${book.available_copies} of ${book.total_copies} on shelf`}
        </span>
        {onBorrow && (
          <button
            onClick={borrow}
            disabled={busy || out || disabled || !!stamp}
            className="rounded-md bg-room px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-room-deep disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? 'Borrowing…' : stamp ? (stamp.kind === 'due' ? 'Borrowed' : 'Requested') : 'Borrow'}
          </button>
        )}
      </div>
    </article>
  )
}
