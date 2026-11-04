// Preview chrome device widths (design v3 screens/G.jsx DV): phone 390, tablet 768, desktop 1280.
export type Device = 'phone' | 'tablet' | 'desktop'
export const DEVICES: Record<Device, { px: number; icon: string }> = { phone: { px: 390, icon: 'phone' }, tablet: { px: 768, icon: 'tablet' }, desktop: { px: 1280, icon: 'desk' } }
