<script setup lang="ts">
import SettingsSectionNav from '../../components/SettingsSectionNav.vue'
import type { NavIconName } from '../../components/ui/NavIcon.vue'
import NavIcon from '../../components/ui/NavIcon.vue'
import { computed } from 'vue'
import { moduleEnabled, type ModuleKey } from '../../services/modules'
import { useSettingsGroup, type SettingsGroupKey } from '../../composables/useSettingsGroup'

// The admin "Settings" hub (route /admin/content, kept for old bookmarks): static, site-wide
// sections that do not change often. Add a new sub-section to the group it belongs to.
type Section = { title: string; description: string; to: string; icon: NavIconName; module?: ModuleKey }

// Grouped by type of activity; the tab strip shows one group at a time (see the template).
const allGroups: { key: SettingsGroupKey; label: string; sections: Section[] }[] = [
  {
    key: 'site',
    label: 'Site',
    sections: [
      {
        title: 'Site availability',
        description: 'Under-construction switch and which pages are visible or published.',
        to: '/admin/content/settings',
        icon: 'globe',
      },
      {
        title: 'Contact details',
        description: 'Email, phone and address shown on the public Contact page.',
        to: '/admin/content/contact-details',
        icon: 'phone',
      },
      {
        title: 'Typography',
        description: 'Choose the description typeface used across the site.',
        to: '/admin/content/typography',
        icon: 'type',
      },
      {
        title: 'Payments',
        description: 'Switch Vipps-App payments on for customers.',
        to: '/admin/content/payments',
        icon: 'credit-card',
        module: 'payments',
      },
      {
        title: 'Header & footer',
        description: 'Top bar, logo size, name style, footer text and social links.',
        to: '/admin/content/header-footer',
        icon: 'globe',
      },
    ],
  },
  {
    key: 'people',
    label: 'People',
    sections: [
      {
        title: 'Committee',
        description: 'Manage who appears on the public Committee page.',
        to: '/admin/content/committee',
        icon: 'users',
        module: 'committee',
      },
      {
        title: 'Founders',
        description: 'Manage the founder quotes shown on the About page.',
        to: '/admin/content/founders',
        icon: 'quote',
        module: 'founders',
      },
      {
        title: 'Sponsors',
        description: 'Manage the sponsor logos scrolling on the home page.',
        to: '/admin/content/sponsors',
        icon: 'award',
        module: 'sponsors',
      },
    ],
  },
  {
    key: 'pages',
    label: 'Pages & media',
    sections: [
      { title: 'Home', description: 'Your own headline, introduction and numbers on the home page.', to: '/admin/content/home', icon: 'globe' },
      { title: 'Events', description: 'The title and intro at the top of the events list.', to: '/admin/content/pages/events', icon: 'calendar', module: 'events' },
      { title: 'Gallery', description: 'The title and intro of the gallery, and the band under the albums.', to: '/admin/content/pages/gallery', icon: 'image', module: 'gallery' },
      { title: 'News', description: 'The title and intro of the news page, and the newsletter band.', to: '/admin/content/pages/news', icon: 'file-text', module: 'news' },
      { title: 'Newsletter sign-up', description: 'The words of the newsletter sign-up: the title, text and the line about what subscribing means.', to: '/admin/content/pages/newsletter', icon: 'mail', module: 'newsletter' },
      { title: 'Membership', description: 'The title and intro of the membership page, and its reasons and steps.', to: '/admin/content/pages/membership', icon: 'credit-card', module: 'memberships' },
      { title: 'Contact', description: 'The title and intro of the contact page, its questions and footnote.', to: '/admin/content/pages/contact', icon: 'phone' },
      { title: 'Committee', description: 'The title and intro at the top of the public Committee page.', to: '/admin/content/pages/committee', icon: 'users', module: 'committee' },
      { title: 'About', description: 'The About page: title, photo, story text, what you stand for, timeline and how to get involved.', to: '/admin/content/pages/about', icon: 'type' },
      { title: 'Legal texts', description: 'Your Privacy Policy and Terms of Sale, shown on the public pages.', to: '/admin/content/legal-texts', icon: 'file-text' },
    ],
  },
]

// The tab strip picks one group (?group=…); the hub shows only that group's cards.
const active = useSettingsGroup()
// A module the owner turned off has no card (W8-R9).
const groups = computed(() => allGroups.filter((g) => g.key === active.value).map((g) => ({ ...g, sections: g.sections.filter((section) => moduleEnabled(section.module)) })))
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div class="ds-heading">
      <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
      <h1 class="ds-display ds-display-s">Settings</h1>
      <p class="ds-intro">Site-wide settings and content that do not change often.</p>
    </div>

    <SettingsSectionNav />

    <template v-for="group in groups" :key="group.key">
      <section class="settings-group" :aria-label="group.label">
        <h2 class="ds-eyebrow settings-group-label">{{ group.label }}</h2>
        <!-- auto-fill (not auto-fit) keeps a lone tile at one column's width, aligned with the other groups. -->
        <div class="ds-cards" style="grid-template-columns: repeat(auto-fill, minmax(260px, 1fr))">
          <router-link v-for="section in group.sections" :key="section.to" :to="section.to" class="ds-card ds-card-interactive" style="display: flex; gap: var(--ds-space-4); align-items: flex-start">
            <NavIcon :name="section.icon" style="width: 24px; height: 24px; flex-shrink: 0; color: var(--ds-text-primary)" />
            <div>
              <p class="ds-card-title">{{ section.title }}</p>
              <p class="ds-meta" style="margin-top: 4px">{{ section.description }}</p>
            </div>
          </router-link>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.settings-group {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-4);
}
.settings-group-label {
  margin: 0;
}
</style>
