/**
 * Renders the tiny formatting the AI is allowed to use: paragraphs, "- " bullets, **bold**, *italic*.
 * Builds React elements only (never innerHTML), so model output can't inject HTML or scripts.
 */
function inline(text, keyBase) {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).filter(Boolean)
  return parts.map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**')) return <strong key={`${keyBase}-${i}`}>{p.slice(2, -2)}</strong>
    if (p.startsWith('*') && p.endsWith('*') && p.length > 2) return <em key={`${keyBase}-${i}`}>{p.slice(1, -1)}</em>
    return p
  })
}

export default function RichText({ text, className = '' }) {
  const blocks = text.trim().split(/\n\s*\n/)
  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {blocks.map((block, b) => {
        const lines = block.split('\n').map((l) => l.trim()).filter(Boolean)
        if (lines.every((l) => /^[-•]\s+/.test(l))) {
          return (
            <ul key={b} className="list-disc pl-5">
              {lines.map((l, i) => <li key={i}>{inline(l.replace(/^[-•]\s+/, ''), `${b}-${i}`)}</li>)}
            </ul>
          )
        }
        return <p key={b}>{lines.map((l, i) => <span key={i}>{i > 0 && <br />}{inline(l, `${b}-${i}`)}</span>)}</p>
      })}
    </div>
  )
}
