// The tab icon of a served square: its first letter in a ring, drawn as an SVG (rootsquares W6-R42). bca-oslo shipped its own logo as favicon.png.
export function squareFaviconHref(name: string): string {
  const letter = (name.trim().charAt(0) || '·').toUpperCase().replace(/[<>&"']/g, '')
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><circle cx="32" cy="32" r="28" fill="#FDF8F1" stroke="#A8422A" stroke-width="5"/>` +
    `<text x="32" y="43" text-anchor="middle" font-family="Georgia,serif" font-size="32" font-weight="600" fill="#4A3627">${letter}</text></svg>`
  return `data:image/svg+xml,${encodeURIComponent(svg)}`
}

export function applySquareFavicon(name: string, logoUrl = ''): void {
  let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }
  if (logoUrl) {
    link.removeAttribute('type') // the browser reads it from the file
    link.href = logoUrl
    return
  }
  link.type = 'image/svg+xml'
  link.href = squareFaviconHref(name)
}
