import { plans, caseStats, type Plan, type CaseStat } from '@/mock/marketing'

// Mock service: same shape a real API client would have, so components stay unchanged later.
const delay = <T>(value: T, ms = 120) => new Promise<T>((resolve) => setTimeout(() => resolve(value), ms))

export const getPlans = (): Promise<Plan[]> => delay(plans)
export const getCaseStats = (): Promise<CaseStat[]> => delay(caseStats)

export interface ContactRequest { name: string; email: string; type: string; organisation?: string; message: string }
export const sendContact = (_request: ContactRequest): Promise<{ ok: true }> => delay({ ok: true as const }, 600)
