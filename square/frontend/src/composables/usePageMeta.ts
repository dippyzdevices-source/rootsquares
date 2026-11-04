import { squareProfile } from '../services/squareConfig'

const SITE_NAME = squareProfile.name // the square's own name (W6-R36)

/** A sleeping square (W17-R24): "<name> — back soon" and a robots tag so search engines do not index the resting page. */
export function setBackSoonMeta(): void {
  document.title = `${SITE_NAME} — back soon`
  let tag = document.querySelector('meta[name="robots"]')
  if (!tag) {
    tag = document.createElement('meta')
    tag.setAttribute('name', 'robots')
    document.head.appendChild(tag)
  }
  tag.setAttribute('content', 'noindex')
}

export function setPageMeta(title: string, description?: string): void {
  document.title = title ? `${title} — ${SITE_NAME}` : SITE_NAME

  if (!description) return

  let tag = document.querySelector('meta[name="description"]')
  if (!tag) {
    tag = document.createElement('meta')
    tag.setAttribute('name', 'description')
    document.head.appendChild(tag)
  }
  tag.setAttribute('content', description)
}
