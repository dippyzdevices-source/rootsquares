import type { BillingOrder } from '@/services/platform'

/** The words for one payment, the same on the Payments page and on its invoice (W19-R16). `t` is vue-i18n's translate function. */
export function orderText(t: (key: string, params?: Record<string, unknown>) => string, o: BillingOrder): string {
  const pkg = () => t(`marketing.pricing.launch.${o.launch_package}.name`)
  if (o.kind === 'event_pass') return t('portal.checkout.eventPass')
  if (o.kind === 'first') return t('portal.checkout.first', { package: pkg() })
  if (o.kind === 'event_upgrade') return t('portal.checkout.eventUpgrade', { package: pkg() })
  if (o.kind === 'upgrade') return t('portal.checkout.upgrade', { package: pkg() })
  return t('portal.checkout.running', { plan: t(`marketing.pricing.running.${o.running_plan}.name`), interval: t(o.interval === 'year' ? 'portal.checkout.year' : 'portal.checkout.month') })
}
