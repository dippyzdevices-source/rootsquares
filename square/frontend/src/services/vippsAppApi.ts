const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export interface VippsAppConfig {
  enabled: boolean
  surcharge_percent: number
}

export async function fetchVippsAppConfig(): Promise<VippsAppConfig> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/payments/vipps-app`)
    if (!response.ok) return { enabled: false, surcharge_percent: 0 }
    return (await response.json()) as VippsAppConfig
  } catch {
    return { enabled: false, surcharge_percent: 0 }
  }
}

/** Whether paying by card (Stripe) is offered right now, and its fee. */
export async function fetchStripeConfig(): Promise<VippsAppConfig> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/payments/stripe`)
    if (!response.ok) return { enabled: false, surcharge_percent: 0 }
    return (await response.json()) as VippsAppConfig
  } catch {
    return { enabled: false, surcharge_percent: 0 }
  }
}

/** Display only — the backend computes the real fee (same round-half-up on øre). */
export function vippsAppFee(baseAmount: number, percent: number): number {
  return Math.floor((baseAmount * percent + 50) / 100)
}

export async function checkVippsReturn(reference: string, cancelled = false): Promise<{ status: string; order_number: string | null; donation_reference?: string; provider?: string }> {
  const response = await fetch(`${API_BASE_URL}/api/payments/vipps-return`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reference, cancelled }),
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json() as Promise<{ status: string; order_number: string | null; donation_reference?: string; provider?: string }>
}
