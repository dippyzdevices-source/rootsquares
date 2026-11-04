// A referral link is the platform's address with ?ref=CODE (W14-R27, docs/reference/prices-and-vouchers.md). The code is kept in this browser for 30 days and filled into the
// voucher box where a payment starts. It only names a code: nothing is applied or checked until the customer pays, and a code that is not valid is simply refused then.
const KEY = 'rs-referral'
const DAYS = 30

export function captureReferral(search: string = typeof window !== 'undefined' ? window.location.search : ''): void {
  try {
    const code = new URLSearchParams(search).get('ref')?.trim().toUpperCase()
    if (code && /^[A-Z0-9][A-Z0-9-]{2,39}$/.test(code)) window.localStorage.setItem(KEY, JSON.stringify({ code, until: Date.now() + DAYS * 86_400_000 }))
  } catch { /* storage blocked: the link just does not prefill anything */ }
}

export function savedReferral(): string {
  try {
    const saved = JSON.parse(window.localStorage.getItem(KEY) ?? 'null') as { code?: string; until?: number } | null
    return saved?.code && (saved.until ?? 0) > Date.now() ? saved.code : ''
  } catch {
    return ''
  }
}
