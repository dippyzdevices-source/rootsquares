// A link like /squares/<id>/settings#mail-domain scrolls to that card. The router tries once, before the page and its cards are drawn, so a page calls this
// when it is shown: it looks for the element for two seconds (a card may fetch its own data first). W25-R35.
export function scrollToHash(hash: string, tries = 20): void {
  const id = hash.replace(/^#/, '')
  if (!id) return
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ block: 'start', behavior: 'smooth' })
  else if (tries > 0) setTimeout(() => scrollToHash(hash, tries - 1), 100)
}
