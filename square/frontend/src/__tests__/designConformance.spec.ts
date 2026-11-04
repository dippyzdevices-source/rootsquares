// Design-system guard: fails when a page hand-rolls a control that has a shared component.
// Each rule explains the component to use instead. If a rule fires on something that is
// genuinely different, add the file to ALLOWED with a reason — don't weaken the rule.
import { describe, it, expect } from 'vitest'

// Every .vue file in src, as raw text (Vite's glob import — no Node typings needed).
const raw = import.meta.glob('../**/*.vue', { query: '?raw', import: 'default', eager: true }) as Record<string, string>
const files = Object.entries(raw).map(([key, text]) => ({ path: key.replace(/^\.\.\//, ''), text }))

// Only the template/markup is checked — the shared components' own <script>/<style> may mention these.
function markup(text: string): string {
  return text.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<style[\s\S]*?<\/style>/g, '').replace(/<!--[\s\S]*?-->/g, '')
}

interface Rule {
  name: string
  use: string
  pattern: RegExp
  // Files that legitimately own or showcase the control.
  exempt: string[]
  // Known leftovers still to convert. The test requires this list to match reality exactly, so it
  // can only shrink: fixing a file makes the test ask you to delete it from here.
  debt?: string[]
}

const RULES: Rule[] = [
  {
    name: 'native <select>',
    use: 'BaseSelect (components/ui) — the themed listbox',
    pattern: /<select\b/,
    exempt: ['pages/dev/ThemeReviewView.vue'], // dev-only review page
  },
  {
    name: 'native file input',
    use: 'BaseFileButton (components/ui)',
    pattern: /<input[^>]*type="file"/,
    exempt: ['components/ui/BaseFileButton.vue'],
    debt: [
      'components/HeritageMediaCards.vue',
      'components/ui/RichTextEditor.vue',
      'pages/admin/AccountingExpenseModal.vue',
      'pages/admin/AdminCommitteeFormView.vue',
      'pages/admin/AdminFoundersFormView.vue',
      'pages/admin/AdminMagazinesFormView.vue',
      'pages/admin/AdminSponsorsFormView.vue',
    ],
  },
  {
    name: 'search input built by hand',
    use: 'BaseSearchField (components/ui) — pill-shaped, with clear button',
    pattern: /<input[^>]*type="search"/,
    exempt: ['components/ui/BaseSearchField.vue', 'pages/dev/ThemeReviewView.vue'],
  },
  {
    name: 'hand-written .ds-btn',
    use: 'BaseButton (components/ui) — pick a variant/size instead of copying classes',
    pattern: /class="[^"]*\bds-btn\b/,
    exempt: [
      'components/ui/BaseButton.vue',
      'components/ui/BaseFileButton.vue',
      'pages/StyleGuideView.vue',
      // A decorative "Read more" span inside an already-clickable featured-article card (not a control).
      'pages/public/NewsListView.vue',
    ],
  },
  {
    name: 'hand-written .ds-icon-btn',
    use: 'BaseIconButton (components/ui) — always with a label/tooltip',
    // Arrows that sit on photos or dark panels (-scrim / -onDark) are their own variants and are fine.
    pattern: /<button[^>]*class="(?![^"]*(?:-scrim|-onDark))[^"]*\bds-icon-btn\b/,
    exempt: ['components/ui/BaseIconButton.vue'],
    // BaseModal's close buttons and the lightbox/event-gallery arrows are part of those shared widgets.
    debt: [
      'components/ui/BankPaymentPanel.vue', // the same close button as VippsPaymentPanel
      'components/ui/BaseModal.vue',
      'components/ui/VippsPaymentPanel.vue',
      'pages/public/NewsDetailView.vue',
    ],
  },
  {
    name: 'inline danger/success colour on a control',
    use: 'variant="danger" / "success" / "warning" on BaseButton or BaseIconButton',
    pattern: /<Base(?:Icon)?Button[^>]*style="[^"]*(?:danger-ink|status-danger|status-success)/,
    exempt: [],
  },
  {
    name: 'hand-written underline <hr style=…>',
    use: '<hr class="ds-section-line" />',
    pattern: /<hr style=/,
    exempt: [],
  },
  {
    name: 'old .ds-select / .ds-select-wrap markup',
    use: 'BaseSelect',
    pattern: /class="[^"]*\bds-select(?:-wrap)?\b/,
    // The volunteer picker is a searchable member menu with its own trigger, not a plain dropdown.
    exempt: ['pages/admin/AdminEventFormView.vue'],
  },
  {
    name: 'hand-written status pills (.ds-toolbar-pills)',
    use: 'FilterPills (components/ui)',
    pattern: /class="ds-toolbar-pills"/,
    exempt: ['components/ui/FilterPills.vue'],
  },
  {
    name: 'toolbar built without .ds-toolbar (search + select in a hand-made flex row)',
    use: '<div class="ds-toolbar"> with .ds-toolbar-search / .ds-toolbar-select children',
    pattern: /<div style="display: flex[^"]*">\s*<BaseSearchField/,
    exempt: [],
  },
]

describe('design-system conformance', () => {
  for (const rule of RULES) {
    it(`no ${rule.name} — use ${rule.use}`, () => {
      const offenders = files
        .filter((f) => !rule.exempt.includes(f.path))
        .filter((f) => rule.pattern.test(markup(f.text)))
        .map((f) => f.path)
        .sort()
      // New violations fail; so does a fixed file still listed as debt (delete it from `debt`).
      expect(offenders).toEqual([...(rule.debt ?? [])].sort())
    })
  }

  it('a search field styled for the toolbar is always inside a .ds-toolbar row', () => {
    // Without the row it stretches to the full page width instead of the 260–420px toolbar size.
    const offenders = files
      .filter((f) => /ds-toolbar-search/.test(markup(f.text)) && !/class="ds-toolbar( [^"]*)?"/.test(markup(f.text)))
      .map((f) => f.path)
    expect(offenders).toEqual([])
  })

  it('every admin list page keeps the header → underline → toolbar structure', () => {
    // A page that has a toolbar must also have the section underline or a section tab strip above it.
    const offenders = files
      .filter((f) => f.path.startsWith('pages/admin/') && /class="ds-toolbar( [^"]*)?"/.test(f.text))
      .filter((f) => !/ds-section-line|SectionNav/.test(f.text))
      .map((f) => f.path)
    expect(offenders).toEqual([])
  })

  it('every admin page heading is followed by an underline or a tab strip', () => {
    const offenders = files
      .filter((f) => f.path.startsWith('pages/admin/') && /class="ds-heading"/.test(f.text))
      .filter((f) => !/ds-section-line|SectionNav/.test(f.text))
      .map((f) => f.path)
    expect(offenders).toEqual([])
  })
})
