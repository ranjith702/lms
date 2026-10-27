// Each catalog category gets a printed-cloth motif (CSS class `motif-<key>` in index.css).
// Matched by keyword so a librarian's renamed or new category still picks up a sensible pattern.
const MOTIFS = [
  [/computer|program|software|code/i, 'circuit'],
  [/science fiction|sci-?fi|space/i, 'stars'],
  [/fantasy|myth|magic/i, 'runes'],
  [/classic|literature|poetry|novel/i, 'gilt'],
  [/mystery|thriller|crime|detective/i, 'hatch'],
  [/history|past|biograph/i, 'laid'],
  [/science|physics|biology|nature/i, 'cells'],
  [/self|psychology|mind|habit/i, 'ripple'],
]

export function motifFor(categoryName = '') {
  for (const [re, key] of MOTIFS) if (re.test(categoryName)) return key
  return 'plain'
}

export const motifClass = (categoryName) => `motif motif-${motifFor(categoryName)}`
