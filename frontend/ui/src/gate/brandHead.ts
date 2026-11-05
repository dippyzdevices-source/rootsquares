// The public page shell of the platform and admin sites carries no brand (W27-R32): a neutral title and a blank icon, because a static file cannot ask for a passcode.
// Once the site gate is open (or there is none), the application calls this to put its own icon in; the tab titles are set per page by the router.
export function showBrandIcon(href = '/favicon.svg'): void {
  let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }
  link.type = 'image/svg+xml'
  link.href = href
}
