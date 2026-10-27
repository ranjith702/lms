import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import Shelf from '../components/Shelf'
import { BrandMark, useApi } from '../components/ui'
import { motifClass } from '../lib/categories'

// Mirrors backend/app/services/trust_service.py (score formula, INSTANT_MIN=70, APPROVAL_MIN=40). Keep in step.
const trustScore = ({ late, onTime, fines, overdue }) =>
  Math.max(0, Math.min(100, 100 - 10 * late - 15 * fines - (overdue ? 25 : 0) + 2 * onTime))
const verdict = (s) => (s >= 70
  ? { text: 'Borrows instantly', tone: 'text-room-deep' }
  : s >= 40 ? { text: 'Requests go to the librarian first', tone: 'text-[#7a5a17]' }
    : { text: 'Borrowing is paused until things are settled', tone: 'text-stamp' })

export default function Landing() {
  const shelf = useApi(() => api('/public/shelf'))
  const [picked, setPicked] = useState(null)
  const books = shelf.data?.books ?? []
  const cats = shelf.data?.categories ?? []

  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 md:px-8">
        <Link to="/" className="flex items-center gap-2 font-book text-xl font-semibold text-room-deep"><BrandMark />Reading Room</Link>
        <nav className="flex items-center gap-2 text-sm font-semibold">
          <Link to="/login" className="rounded-md px-3 py-2 text-room hover:bg-room-soft">Log in</Link>
          <Link to="/register" className="rounded-md bg-room px-3.5 py-2 text-white hover:bg-room-deep">Create an account</Link>
        </nav>
      </header>

      {/* Hero: the actual shelf is the first thing you see. */}
      <section className="mx-auto max-w-6xl px-4 pt-6 md:px-8 md:pt-12">
        <h1 className="max-w-3xl text-4xl leading-[1.1] font-semibold text-room-deep md:text-6xl">
          The whole reading room, on one shelf.
        </h1>
        <p className="mt-5 max-w-xl text-lg text-ink-soft">
          See what the library holds, borrow in one click, and know the exact day it's due.
          Return books on time and you never wait for approval.
        </p>

        <div className="mt-10 rounded-xl border border-line bg-sheet px-4 pt-8 pb-5 md:px-8">
          {shelf.error && <p className="py-10 text-center text-ink-soft">The shelf couldn't load ({shelf.error}).</p>}
          {shelf.loading && <div className="h-56 animate-pulse rounded-md bg-paper" role="status" aria-label="Loading the shelf" />}
          {books.length > 0 && <Shelf books={books} picked={picked} onPick={setPicked} animate />}
          <div className="mt-5 min-h-12 text-sm text-ink-soft" aria-live="polite">
            {picked ? (
              <p>
                <span className="font-book text-base font-semibold text-ink">{picked.title}</span> by {picked.author},
                in {picked.category_name}. <Link to="/login" className="font-semibold text-room hover:underline">Log in to borrow it</Link>.
              </p>
            ) : books.length > 0 && (
              <p>Live from the catalog: {books.length} books across {cats.length} shelves. Pick a spine to take it out.</p>
            )}
          </div>
        </div>
      </section>

      <TrustSection />
      <AskSection />

      {cats.length > 0 && (
        <section className="mx-auto max-w-6xl px-4 py-16 md:px-8">
          <h2 className="text-3xl font-semibold text-room-deep">What's on the shelves</h2>
          <p className="mt-2 max-w-xl text-ink-soft">Each subject has its own cover pattern, so you can spot it across the catalog.</p>
          <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {cats.map((c) => (
              <li key={c.id} className="flex gap-3 rounded-lg border border-line bg-sheet p-4">
                <span className={`relative h-14 w-10 shrink-0 rounded-sm bg-room ${motifClass(c.name)}`} aria-hidden="true" />
                <div>
                  <p className="font-book font-semibold">{c.name}</p>
                  <p className="text-sm text-ink-soft">{c.description}</p>
                  <p className="mt-1 text-xs font-semibold text-room">{c.book_count} {c.book_count === 1 ? 'book' : 'books'}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-sm text-ink-soft md:px-8">
          <span>Reading Room library</span>
          <span>Loans run 14 days. Late returns cost ₹5 a day.</span>
        </div>
      </footer>
    </div>
  )
}

function Stepper({ label, value, onChange, max = 9 }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <span className="text-sm">{label}</span>
      <div className="flex items-center gap-1">
        <button type="button" onClick={() => onChange(Math.max(0, value - 1))} disabled={value === 0}
          aria-label={`Fewer: ${label}`} className="h-8 w-8 rounded-md border border-line bg-sheet text-lg leading-none hover:border-room disabled:opacity-40">−</button>
        <span className="w-6 text-center font-semibold tabular-nums" aria-live="polite">{value}</span>
        <button type="button" onClick={() => onChange(Math.min(max, value + 1))} disabled={value === max}
          aria-label={`More: ${label}`} className="h-8 w-8 rounded-md border border-line bg-sheet text-lg leading-none hover:border-room disabled:opacity-40">+</button>
      </div>
    </div>
  )
}

function TrustSection() {
  const [r, setR] = useState({ late: 1, onTime: 4, fines: 0, overdue: false })
  const set = (k) => (v) => setR({ ...r, [k]: v })
  const score = trustScore(r)
  const v = verdict(score)
  const x = 20 + score * 6.4   // scale runs from x=20 (0) to x=660 (100)

  return (
    <section className="mt-20 bg-room-soft/60">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 md:grid-cols-[1fr_1.3fr] md:px-8">
        <div>
          <h2 className="text-3xl font-semibold text-room-deep">How borrowing works</h2>
          <p className="mt-3 text-ink-soft">
            Every student has a trust score from 0 to 100, worked out from their own return record. It decides whether a
            borrow goes through straight away. Try a record below.
          </p>
          <div className="mt-6 divide-y divide-line rounded-lg border border-line bg-sheet px-4">
            <Stepper label="Books returned on time (+2 each)" value={r.onTime} onChange={set('onTime')} />
            <Stepper label="Books returned late (−10 each)" value={r.late} onChange={set('late')} />
            <Stepper label="Unpaid fines (−15 each)" value={r.fines} onChange={set('fines')} />
            <label className="flex items-center justify-between gap-3 py-3 text-sm">
              A book overdue right now (−25)
              <input type="checkbox" className="h-4 w-4 accent-[var(--color-room)]" checked={r.overdue}
                onChange={(e) => set('overdue')(e.target.checked)} />
            </label>
          </div>
        </div>

        <div className="self-center">
          <svg viewBox="0 0 680 190" className="w-full" role="img"
            aria-label={`Trust scale. Below 40 borrowing is paused, 40 to 69 needs approval, 70 and above borrows instantly. This record scores ${score}.`}>
            <rect x="20" y="70" width="256" height="34" rx="6" fill="var(--color-stamp-soft)" />
            <rect x="276" y="70" width="192" height="34" fill="var(--color-brass-soft)" />
            <rect x="468" y="70" width="192" height="34" rx="6" fill="var(--color-room-soft)" />
            {/* square off the inner corners of the two rounded end zones */}
            <rect x="266" y="70" width="10" height="34" fill="var(--color-stamp-soft)" />
            <rect x="468" y="70" width="10" height="34" fill="var(--color-room-soft)" />
            <g fontFamily="var(--font-ui)" fontSize="19" fontWeight="600">
              <text x="148" y="94" textAnchor="middle" fill="var(--color-stamp)">Paused</text>
              <text x="372" y="94" textAnchor="middle" fill="#7a5a17">Needs approval</text>
              <text x="564" y="94" textAnchor="middle" fill="var(--color-room-deep)">Instant</text>
            </g>
            <g fontFamily="var(--font-ui)" fontSize="18" fill="var(--color-ink-soft)" textAnchor="middle">
              {[0, 40, 70, 100].map((n) => (
                <g key={n}>
                  <line x1={20 + n * 6.4} x2={20 + n * 6.4} y1="104" y2="114" stroke="var(--color-ink-soft)" />
                  <text x={20 + n * 6.4} y="136">{n}</text>
                </g>
              ))}
            </g>
            <g className="trust-marker" style={{ transform: `translateX(${x}px)` }}>
              <path d="M0 64 L-9 48 L9 48 Z" fill="var(--color-ink)" />
              <text y="38" textAnchor="middle" fontFamily="var(--font-book)" fontSize="32" fontWeight="700" fill="var(--color-ink)">{score}</text>
            </g>
          </svg>
          <p className={`mt-2 text-center font-book text-xl font-semibold ${v.tone}`}>{v.text}</p>
          <p className="mt-1 text-center text-sm text-ink-soft">Paying a fine or returning an overdue book lifts the score immediately.</p>
        </div>
      </div>
    </section>
  )
}

const ASK_STEPS = [
  ['Your question', 'In your own words: “something like The Martian but with less science”'],
  ['Two searches at once', 'One matches meaning, the other matches exact words and topics'],
  ['Results merged', 'Books found by both searches rise to the top'],
  ['Six books from this library', 'Only titles the reading room actually holds'],
  ['An answer', 'Recommends from those six and says why. Nothing found means no guessing'],
]

function AskSection() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 md:px-8">
      <h2 className="text-3xl font-semibold text-room-deep">Ask the catalog</h2>
      <p className="mt-3 max-w-2xl text-ink-soft">
        Describe the kind of book you want. The assistant searches this library first and only recommends what is
        on the shelf, so every suggestion is something you can borrow today.
      </p>

      {/* Wide screens: the flow as a diagram. */}
      <svg viewBox="0 0 1000 250" className="mt-10 hidden w-full md:block" role="img"
        aria-label="Your question goes to a meaning search and a word search at the same time; the results are merged, the top six books from this library are picked, and the answer recommends only from those.">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 Z" fill="var(--color-ink-soft)" />
          </marker>
        </defs>
        <g fill="none" stroke="var(--color-ink-soft)" strokeWidth="1.6" markerEnd="url(#arrow)">
          <path d="M170 125 C 205 125, 205 62, 238 62" />
          <path d="M170 125 C 205 125, 205 188, 238 188" />
          <path d="M418 62 C 452 62, 452 125, 488 125" />
          <path d="M418 188 C 452 188, 452 125, 488 125" />
          <path d="M638 125 L 688 125" />
          <path d="M838 125 L 868 125" />
        </g>
        <FlowBox x={10} y={95} w={160} title="Your question" sub="plain words" tone="ink" />
        <FlowBox x={240} y={32} w={178} title="Meaning search" sub="similar ideas, any wording" tone="room" />
        <FlowBox x={240} y={158} w={178} title="Word search" sub="titles, authors, topics" tone="room" />
        <FlowBox x={490} y={95} w={148} title="Merge" sub="agreement ranks higher" tone="brass" />
        <FlowBox x={690} y={95} w={148} title="Top 6 books" sub="all on this shelf" tone="brass" />
        <FlowBox x={870} y={95} w={120} title="Answer" sub="names only those" tone="ink" />
      </svg>

      {/* Narrow screens: the same steps, in order. */}
      <ol className="mt-8 flex flex-col gap-3 md:hidden">
        {ASK_STEPS.map(([t, d], i) => (
          <li key={t} className="flex gap-3 rounded-lg border border-line bg-sheet p-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-room text-sm font-semibold text-white">{i + 1}</span>
            <div><p className="font-semibold">{t}</p><p className="text-sm text-ink-soft">{d}</p></div>
          </li>
        ))}
      </ol>
    </section>
  )
}

function FlowBox({ x, y, w, title, sub, tone }) {
  const fill = { ink: 'var(--color-sheet)', room: 'var(--color-room-soft)', brass: 'var(--color-brass-soft)' }[tone]
  return (
    <g>
      <rect x={x} y={y} width={w} height="60" rx="8" fill={fill} stroke="var(--color-line)" />
      <text x={x + w / 2} y={y + 26} textAnchor="middle" fontFamily="var(--font-book)" fontSize="17" fontWeight="600" fill="var(--color-ink)">{title}</text>
      <text x={x + w / 2} y={y + 45} textAnchor="middle" fontFamily="var(--font-ui)" fontSize="12.5" fill="var(--color-ink-soft)">{sub}</text>
    </g>
  )
}
