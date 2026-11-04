// "Try it at checkout" on the Vouchers page (W19-R35): what a customer would pay for a price when they type some of the platform's codes. It repeats the
// arithmetic of backend/app/platform/vouchers.py (`discount_for`, `evaluate_codes`) so the owner sees the effect of the stacking setting before saving it.
// It only plays with the price: validity dates, packages and use limits are not checked here; the real checkout does that.

export interface SimVoucher { code: string; kind: 'percent' | 'fixed'; value: number; stackable: boolean }
export type SimWhy = 'extra' | 'worse' | 'notStackable' | 'nothingLeft'
export interface SimResult { used: { code: string; off: number }[]; ignored: { code: string; why: SimWhy }[]; payable: number }

/** What one code takes off `base` (minor units): a percent rounded to the nearest unit, or a fixed amount, never more than the base. */
export function discountFor(v: SimVoucher, base: number): number {
  if (base <= 0) return 0
  const raw = v.kind === 'percent' ? Math.floor((base * v.value + 50) / 100) : v.value
  return Math.max(0, Math.min(raw, base))
}

export function simulate(price: number, typed: SimVoucher[], mode: 'best' | 'sequential' | 'additive', max: number): SimResult {
  const within = typed.slice(0, Math.max(1, max))
  const ignored: SimResult['ignored'] = typed.slice(within.length).map((v) => ({ code: v.code, why: 'extra' }))
  const used: SimResult['used'] = []
  if (!within.length) return { used, ignored, payable: price }
  if (within.length === 1) {
    const off = discountFor(within[0]!, price)
    return { used: [{ code: within[0]!.code, off }], ignored, payable: price - off }
  }
  if (mode === 'best') {
    let best = within[0]!
    for (const v of within) if (discountFor(v, price) > discountFor(best, price)) best = v
    for (const v of within) if (v !== best) ignored.push({ code: v.code, why: 'worse' })
    const off = discountFor(best, price)
    return { used: [{ code: best.code, off }], ignored, payable: price - off }
  }
  let left = price // what the codes may still take off
  for (const v of within) {
    if (!v.stackable) { ignored.push({ code: v.code, why: 'notStackable' }); continue }
    const given = Math.min(discountFor(v, mode === 'sequential' ? left : price), left)
    if (given <= 0) { ignored.push({ code: v.code, why: 'nothingLeft' }); continue }
    left -= given
    used.push({ code: v.code, off: given })
  }
  return { used, ignored, payable: left }
}
