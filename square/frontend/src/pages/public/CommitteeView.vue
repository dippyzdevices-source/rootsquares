<script setup lang="ts">
import PageHeading from '../../layout-themes/parts/PageHeading.vue'
import { activeLayout } from '../../layout-themes/layouts'
const themed = activeLayout !== null // a layout theme sets the page heading and lists (W9-R5)
import { usePageHeading } from '../../composables/usePageHeading'
import { squareProfile } from '../../services/squareConfig'
import { ref, onMounted } from 'vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { fetchCommittee, type CommitteeMember } from '../../services/committeeApi'

const members = ref<CommitteeMember[]>([])
const loading = ref(true)
const error = ref(false)

onMounted(async () => {
  try {
    members.value = (await fetchCommittee()).items
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})
const heading = usePageHeading('committee', () => ({ eyebrow: 'Organisation', title: 'Our committee', intro: `The volunteers who run ${squareProfile.name}.` }))
</script>

<template>
  <div class="ds-scope">
    <PageHeading v-if="themed" :heading="heading" />
    <section v-else class="ds-band ds-band-wash" style="padding-bottom: var(--ds-space-6)">
      <div class="ds-container ds-heading">
        <span v-if="heading.script_line" class="ds-script">{{ heading.script_line }}</span>
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />{{ heading.eyebrow }}</span>
        <h1 class="ds-display ds-display-m">{{ heading.title }}</h1>
        <p v-if="heading.local_line" class="ds-bn" style="font-size: var(--ds-text-subtitle); color: var(--ds-text-muted)">{{ heading.local_line }}</p>
        <p class="ds-intro">{{ heading.intro }}</p>
      </div>
    </section>

    <section class="ds-band ds-band-paper" style="padding-top: var(--ds-space-6)">
      <div class="ds-container">
        <BaseLoadingState v-if="loading" label="Loading the committee…" />
        <BaseEmptyState
          v-else-if="error"
          title="Couldn't load the committee"
          description="Please try again shortly."
        />
        <BaseEmptyState
          v-else-if="members.length === 0"
          title="No committee members yet"
          description="Check back soon."
        />
        <div v-else class="ds-cards ds-cards--2">
          <article v-for="member in members" :key="member.id" class="ds-portrait-card">
            <div class="ds-portrait-top">
            <div class="ds-portrait-left">
              <div class="ds-portrait-name-block">
                <p v-if="member.role" class="ds-portrait-role">{{ member.role }}</p>
                <span v-if="member.published === false" class="ds-badge ds-badge-neutral draft-pill">Draft</span>
                <h2 class="ds-portrait-name">{{ member.name }}</h2>
                <p v-if="member.sub_name" class="ds-meta ds-portrait-subname">{{ member.sub_name }}</p>
                <div class="ds-motif" style="margin: var(--ds-space-3) 0; max-width: none" aria-hidden="true">
                  <span></span><span class="ds-motif-glyph">❖</span><span></span>
                </div>
                <div v-if="member.address || member.email || member.phone || member.member_since" class="ds-portrait-lines">
                  <div v-if="member.address" class="ds-portrait-line">
                    <span class="ds-portrait-line-icon" aria-hidden="true" title="Address">⌂</span>
                    <span class="ds-portrait-line-value">{{ member.address }}</span>
                  </div>
                  <div v-if="member.email" class="ds-portrait-line">
                    <span class="ds-portrait-line-icon" aria-hidden="true" title="Email">@</span>
                    <a :href="`mailto:${member.email}`" class="ds-portrait-line-link">{{ member.email }}</a>
                  </div>
                  <div v-if="member.phone" class="ds-portrait-line">
                    <span class="ds-portrait-line-icon" aria-hidden="true" title="Phone">☎</span>
                    <a :href="`tel:${member.phone.replace(/\s/g, '')}`" class="ds-portrait-line-link">{{ member.phone }}</a>
                  </div>
                  <div v-if="member.member_since" class="ds-portrait-line">
                    <span class="ds-portrait-line-icon" aria-hidden="true" title="Member since">✦</span>
                    <span class="ds-portrait-line-value">Member since {{ member.member_since }}</span>
                  </div>
                </div>
              </div>
              <div v-if="member.address || member.email || member.phone || member.member_since" class="ds-motif" style="margin: auto 0 0; max-width: none" aria-hidden="true">
                <span></span><span class="ds-motif-glyph">❖</span><span></span>
              </div>
            </div>
            <div class="ds-portrait-thumb">
              <img v-if="member.portrait_url" :src="member.portrait_url" :alt="member.name" />
              <div v-else class="ds-placeholder" style="width: 100%; height: 100%"><span class="ds-placeholder-glyph">✺</span></div>
            </div>
            </div>
            <figure v-if="member.quote" class="ds-portrait-quote">
              <span class="ds-portrait-quote-mark" aria-hidden="true">&ldquo;</span>
              <blockquote class="ds-portrait-quote-text">{{ member.quote }}</blockquote>
            </figure>
          </article>
        </div>
      </div>
    </section>
  </div>
</template>
