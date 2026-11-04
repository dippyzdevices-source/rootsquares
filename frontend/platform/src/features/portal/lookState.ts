/** What the own-look card tells the Theme page (W18-R30): whether its draft differs from what is saved, and the names shown on the page's tabs. */
export interface LookState {
  dirty: boolean
  hasAny: boolean
  hasSaved: boolean
  busy: boolean
  allowed: boolean
  colourName: string
  fontName: string
  shapeName: string
  feelName: string
  kept: number
}
