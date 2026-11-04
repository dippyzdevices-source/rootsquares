/**
 * What it is:   The starting looks of the Theme page's "Looks" tab (rootsquares W18-R46, docs/plans/themes-starting-looks-plan.md).
 * What it does: A starting look is a named bundle of the owner's own choices: one colour scheme (COLOUR_SCHEMES id), one font pair (FONT_PAIRS id), shapes and feel (ids of SHAPE_PARTS and FEEL_PARTS).
 *               It is no new kind of data: choosing one fills the same colours, fonts, shape and feel that the other tabs fill, and the owner changes any part afterwards. The spinners and the theme itself are never touched.
 * How to use:   import { STARTING_LOOKS }; features/portal/ThemeLookCard.vue shows them and fills the draft.
 * Run:          from frontend: npm run test:look (a test checks that every id exists).
 * Read before:  src/themes/lookPresets.ts.
 * Read after:   features/portal/ThemeLookCard.vue.
 */
import type { FeelLookChoice, ShapeLookChoice } from './lookPresets'

export interface StartingLook { id: string; name: string; hint: string; scheme: string; fonts: string; shape: ShapeLookChoice; feel: FeelLookChoice }

export const STARTING_LOOKS: StartingLook[] = [
  { id: 'community-hall', name: 'Warm community hall', hint: 'Terracotta, soft corners, a friendly serif', scheme: 'paper-brick', fonts: 'warm',
    shape: { buttons: 'soft', cards: 'rounded', photos: 'rounded', edges: 'flat' }, feel: { density: 'comfortable', motion: 'lively' } },
  { id: 'classic-formal', name: 'Classic and formal', hint: 'Oxblood, square corners, thin lines', scheme: 'ledger-gazette', fonts: 'scholarly',
    shape: { buttons: 'square', cards: 'square', photos: 'square', edges: 'line' }, feel: { density: 'comfortable', divider: 'glyph' } },
  { id: 'modern-clean', name: 'Modern and clean', hint: 'Electric blue, soft corners, plain lines', scheme: 'fjord-modern', fonts: 'clean',
    shape: { buttons: 'soft', cards: 'soft', photos: 'soft', edges: 'flat' }, feel: { motion: 'calm', divider: 'line' } },
  { id: 'friendly-playful', name: 'Friendly and playful', hint: 'Fuchsia, pill buttons, airy spacing', scheme: 'fuchsia-pop', fonts: 'playful',
    shape: { buttons: 'pill', cards: 'rounded', photos: 'rounded', edges: 'flat' }, feel: { density: 'airy', motion: 'lively' } },
  { id: 'elegant-arch', name: 'Elegant', hint: 'Orchid, arched photos, fine serif', scheme: 'orchid-dusk', fonts: 'elegant',
    shape: { buttons: 'soft', cards: 'soft', photos: 'arch', edges: 'line' }, feel: { density: 'airy', divider: 'glyph' } },
  { id: 'night-stage', name: 'Night stage', hint: 'Starts dark, pewter, strong lines, pill buttons', scheme: 'graphite', fonts: 'bold',
    shape: { buttons: 'pill', cards: 'soft', photos: 'soft', edges: 'strong' }, feel: { mode: 'dark', density: 'comfortable' } },
  { id: 'easy-to-read', name: 'Calm and easy to read', hint: 'Large text, no hover effects, plain lines', scheme: 'dusk-blue', fonts: 'clean',
    shape: { buttons: 'soft', cards: 'soft', photos: 'soft', edges: 'line' }, feel: { text: 'large', density: 'airy', motion: 'calm', divider: 'line' } },
  { id: 'earthy-natural', name: 'Earthy and natural', hint: 'Olive, rounded photos, soft rounded type', scheme: 'olive-linen', fonts: 'soft',
    shape: { buttons: 'rounded', cards: 'rounded', photos: 'rounded', edges: 'flat' }, feel: { density: 'airy' } },
  { id: 'bold-sharp', name: 'Bold and sharp', hint: 'Ruby, square corners, strong lines, compact', scheme: 'ruby-pop', fonts: 'dramatic',
    shape: { buttons: 'square', cards: 'square', photos: 'square', edges: 'strong' }, feel: { density: 'compact' } },
  { id: 'coastal-calm', name: 'Coastal and calm', hint: 'Sand and teal, soft corners, light editorial type', scheme: 'sand-teal', fonts: 'contemporary',
    shape: { buttons: 'rounded', cards: 'soft', photos: 'soft', edges: 'shadow' }, feel: { density: 'comfortable', motion: 'calm', divider: 'line' } },
]
