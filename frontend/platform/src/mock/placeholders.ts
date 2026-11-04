// PLACEHOLDER VALUES. Nothing here is real. Every figure shown in marketing copy, pricing and the BCA case study comes from this file
// (listed in MISSING.md "Placeholder values"). Replace with real values before launch.

export const PLAN_PRICE_KR = { small: 0, community: 290, federation: 790 } as const // design v4 placeholders, NOK per month (monthly billing)
export const PLAN_PRICE_YEARLY_KR = { small: 0, community: 240, federation: 650 } as const // per month when billed yearly (save 17%)

export const CASE_FIGURES = { launchMinutes: 47, members: 40, festivals: 4, spreadsheets: 0 } as const // BCA Oslo numbers are invented
export const CASE_STRIP = ['700+', '120+', '400+'] as const // case study figure strip: tickets sold online, members, guests: the owner's own figures (W26-R44)

export const VIPPS_DEMO_NUMBER = '123 45 678' // demo Vipps number shown after an order

// DNS records shown on the Domain screen (invented; 203.0.113.10 is a documentation address)
export const DOMAIN_RECORDS = [
  { type: 'CNAME', name: 'www', value: 'sites.rootsquares.net', ttl: '3600' },
  { type: 'TXT', name: '_rs-verify', value: 'rs-verify=4f9a2c71e0b84d', ttl: '3600' },
  { type: 'A', name: '@', value: '203.0.113.10', ttl: '3600' },
]
