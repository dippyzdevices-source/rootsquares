import './demo/install' // demo mode (W10-R14) must come first: it replaces fetch before squareConfig asks the server who this square is
import './services/supportSession' // a support session's token is taken out of the address before anything reads it (W23-R66)
import { demoActive } from './demo/install'
import { gateIsOpen } from './services/gate'

// A private (staging) deploy has a site gate (ADR 099, W26-R20): the server refuses every /api/ request without the pass a passcode earns, and the square's own
// configuration is one of those requests. So the gate is asked FIRST, before the rest of the site (boot.ts) is loaded; until this browser has its pass only the
// passcode screen is shown. No gate (the normal case) and demo mode pass at once.
void (async () => {
  if (demoActive() || (await gateIsOpen())) {
    await import('./boot')
    return
  }
  const { showGate } = await import('./gate/showGate')
  showGate()
})()
