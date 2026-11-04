import type { OwnerAttention } from '../adminTypes'

// Where the button of a "Needs attention" line goes (W25-R33): the part of the square page where the item is handled. Used by the Needs attention page and the
// Overview card. The anchors are `#mail-domain` (OwnerMailDomain) and `#support` (SupportCard); `?tab=actions` opens the Actions tab.
export function attentionLink(a: OwnerAttention): string {
  const base = `/squares/${a.square_id}`
  if (a.kind === 'mail_domain_requested' || a.kind === 'mail_domain_help') return `${base}?tab=actions#mail-domain`
  if (a.kind === 'site_domain_requested' || a.kind === 'site_domain_help') return `${base}?tab=actions#site-domain`
  if (a.kind === 'support_granted') return `${base}#support`
  if (a.kind === 'google_requested') return `${base}?tab=actions`
  return base
}
