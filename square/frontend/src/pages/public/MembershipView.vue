<script setup lang="ts">
import MembershipBlock from '../../layout-themes/sections/MembershipBlock.vue'
import PageHeading from '../../layout-themes/parts/PageHeading.vue'
import { activeLayout } from '../../layout-themes/layouts'
const themed = activeLayout !== null // a layout theme sets the page heading and lists (W9-R5)
import { moduleEnabled } from '../../services/modules'
import { usePageHeading } from '../../composables/usePageHeading'
import { squareProfile } from '../../services/squareConfig'
import { ref, onMounted } from 'vue'
import { EMPTY_MEMBERSHIP_PAGE, loadHomeContent, type MembershipPage } from '../../services/siteContent'
import BaseButton from '../../components/ui/BaseButton.vue'
import JoinMembershipModal from '../../components/JoinMembershipModal.vue'
import { useAuthStore } from '../../stores/auth'
import { fetchMembershipTypes, type MembershipTypeOption } from '../../services/memberApi'
import { fetchTestimonials, type Testimonial } from '../../services/testimonialsApi'
import { formatMembershipPrice } from '../../utils/membership'
import { humanize } from '../../utils/formatEnum'

const auth = useAuthStore()

function displayName(name: string): string {
  return humanize(name)
}

const membershipTypes = ref<MembershipTypeOption[]>([])
const featuredTestimonial = ref<Testimonial | null>(null)
const joinOpen = ref(false)
const joinType = ref<MembershipTypeOption | null>(null)

// Tapping a type opens the small join-and-pay form for it.
function chooseType(type: MembershipTypeOption) {
  joinType.value = type
  joinOpen.value = true
}

onMounted(async () => {
  void loadHomeContent().then((content) => (page.value = content.membership_page))
  try {
    membershipTypes.value = await fetchMembershipTypes()
  } catch {
    membershipTypes.value = []
  }

  if (!moduleEnabled('testimonials')) return
  try {
    const data = await fetchTestimonials()
    featuredTestimonial.value = data.items[0] ?? null
  } catch {
    // Non-critical — the page reads fine without a quote.
  }
})

// Why join and how to join are the square's own words (W7-R11); a list with no lines is not shown.
const page = ref<MembershipPage>({ ...EMPTY_MEMBERSHIP_PAGE })
const heading = usePageHeading('membership', () => ({ eyebrow: 'Membership', title: 'Become a member', intro: `${squareProfile.name} is run by its members, for its members. Joining helps keep everything we do alive for the community — and gets you closer to it in return.` }))
</script>

<template>
  <div class="ds-scope">
    <PageHeading v-if="themed" :heading="heading" />
    <section v-else class="ds-band ds-band-wash">
      <div class="ds-container ds-heading">
        <span v-if="heading.script_line" class="ds-script">{{ heading.script_line }}</span>
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />{{ heading.eyebrow }}</span>
        <h1 class="ds-display ds-display-m">{{ heading.title }}</h1>
        <p v-if="heading.local_line" class="ds-bn" style="font-size: var(--ds-text-subtitle); color: var(--ds-text-muted)">{{ heading.local_line }}</p>
        <p class="ds-intro">{{ heading.intro }}</p>
      </div>
    </section>

    <section v-if="themed" class="lt-sec">
      <div class="lt-cont"><MembershipBlock :items="membershipTypes" :join-to="auth.isAuthenticated ? '/member' : '/register'" /></div>
    </section>

    <section class="ds-band ds-band-paper">
      <div class="ds-container ds-row ds-row--half" style="align-items: start">
        <div class="ds-card" style="padding: var(--ds-space-6); display: flex; flex-direction: column; gap: var(--ds-space-6)">
          <div v-if="page.benefits.length">
            <span v-if="page.benefits_eyebrow" class="ds-eyebrow"><span class="ds-eyebrow-rule" />{{ page.benefits_eyebrow }}</span>
            <ul style="margin-top: var(--ds-space-4); display: flex; flex-direction: column; gap: var(--ds-space-3)">
              <li v-for="(benefit, index) in page.benefits" :key="index" style="display: flex; gap: var(--ds-space-3)" class="ds-body">
                <span style="color: var(--ds-text-primary)">•</span>
                <span>{{ benefit.text }}</span>
              </li>
            </ul>
          </div>

          <div v-if="page.steps.length">
            <span v-if="page.steps_eyebrow" class="ds-eyebrow"><span class="ds-eyebrow-rule" />{{ page.steps_eyebrow }}</span>
            <ol style="margin-top: var(--ds-space-4); display: flex; flex-direction: column; gap: var(--ds-space-3)">
              <li v-for="(step, index) in page.steps" :key="index" style="display: flex; gap: var(--ds-space-3)" class="ds-body">
                <span style="color: var(--ds-text-primary); font-weight: 600">{{ index + 1 }}.</span>
                <span>{{ step.text }}</span>
              </li>
            </ol>
          </div>
        </div>

        <div>
          <span v-if="!themed" class="ds-eyebrow"><span class="ds-eyebrow-rule" />Membership types</span>
          <div v-if="!themed" class="ds-table-wrap" style="margin-top: var(--ds-space-4)">
            <div class="ds-table-scroll">
              <table class="ds-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Price</th>
                    <th>What it's for</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="type in membershipTypes"
                    :key="type.name"
                    :data-type="type.name"
                    class="ds-row-clickable"
                    role="button"
                    tabindex="0"
                    @click="chooseType(type)"
                    @keydown.enter.prevent="chooseType(type)"
                    @keydown.space.prevent="chooseType(type)"
                  >
                    <td data-emphasis>{{ displayName(type.name) }}</td>
                    <td style="white-space: nowrap">
                      <router-link v-if="type.contact_for_price" to="/contact" @click.stop style="color: var(--ds-text-primary); font-weight: 600">
                        Contact us for pricing →
                      </router-link>
                      <span v-else style="color: var(--ds-text-primary); font-weight: 600">{{ formatMembershipPrice(type) }}</span>
                    </td>
                    <td class="ds-meta">{{ type.description ?? '' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <p class="ds-meta" style="margin-top: var(--ds-space-3)">Tap a membership type to join and pay.</p>

          <div style="margin-top: var(--ds-space-5)">
            <BaseButton v-if="auth.isAuthenticated" to="/member" size="lg" full-width>Go to my dashboard</BaseButton>
            <div v-else style="display: flex; gap: var(--ds-space-3); flex-wrap: wrap">
              <BaseButton to="/register" size="lg" style="flex: 1">Create an account</BaseButton>
              <BaseButton to="/login" variant="secondary" size="lg">Log in</BaseButton>
            </div>
          </div>

          <div v-if="featuredTestimonial" class="ds-motif" style="margin: var(--ds-space-6) 0"><span></span><span class="ds-motif-glyph">❖</span><span></span></div>
          <blockquote v-if="featuredTestimonial" class="ds-pullquote">
            <p>&ldquo;{{ featuredTestimonial.quote }}&rdquo;</p>
            <footer>
              <span class="ds-quote-rule" />
              {{ featuredTestimonial.author_name }}<template v-if="featuredTestimonial.author_context">, {{ featuredTestimonial.author_context }}</template>
            </footer>
          </blockquote>
        </div>
      </div>
    </section>
    <JoinMembershipModal v-model="joinOpen" :type="joinType" />
  </div>
</template>
