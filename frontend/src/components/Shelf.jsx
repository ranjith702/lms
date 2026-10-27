import { motifClass } from '../lib/categories'

// Sizes come from the book id and title so the shelf looks hand-stacked but never reshuffles between renders.
const spineHeight = (id) => 150 + ((id * 37) % 6) * 11
const spineWidth = (title) => 26 + (title.length % 4) * 5

/** A wooden shelf of book spines, grouped by category. Clicking a spine selects it (pulls it out). */
export default function Shelf({ books, picked, onPick, animate = false, compact = false }) {
  const sorted = [...books].sort((a, b) =>
    a.category_name.localeCompare(b.category_name) || a.title.localeCompare(b.title))
  const scale = compact ? 0.72 : 1
  const Spine = onPick ? 'button' : 'span'   // without a picker the shelf is decoration, not a control

  return (
    <div className={`flex items-end ${compact ? 'flex-nowrap overflow-hidden' : 'flex-wrap gap-y-6'} ${animate ? 'shelf-animate' : ''}`} aria-hidden={onPick ? undefined : true}>
      {sorted.map((b, i) => (
        <div key={b.id} className="slot">
          <Spine
            type={onPick ? 'button' : undefined}
            className={`spine ${motifClass(b.category_name)}`}
            style={{ background: b.cover_color, height: spineHeight(b.id) * scale, width: spineWidth(b.title) * scale, '--i': i }}
            onClick={onPick ? () => onPick(b) : undefined}
            aria-pressed={onPick ? picked?.id === b.id : undefined}
            aria-label={onPick ? `${b.title} by ${b.author}, ${b.category_name}` : undefined}
            title={`${b.title} — ${b.author}`}
          >
            {!compact && <span className="spine-title">{b.title}</span>}
          </Spine>
        </div>
      ))}
    </div>
  )
}
