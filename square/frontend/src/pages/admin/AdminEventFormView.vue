<script setup lang="ts">
import { moduleEnabled, type ModuleKey } from '../../services/modules'
import { squareProfile } from '../../services/squareConfig'
import EventRepeatCard from '../../components/EventRepeatCard.vue'
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseAvatar from '../../components/ui/BaseAvatar.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import BaseRadio from '../../components/ui/BaseRadio.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseFileButton from '../../components/ui/BaseFileButton.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import RichTextEditor from '../../components/ui/RichTextEditor.vue'
import {
  createAdminEvent,
  fetchAdminEvent,
  updateAdminEvent,
  uploadEventBanner,
  addEventBanner,
  deleteEventBanner,
  ValidationError,
  type AdminEvent,
  type EventBanner,
  type EventPayload,
} from '../../services/adminEventsApi'
import {
  createEventSession,
  updateEventSession,
  deleteEventSession,
  ValidationError as SessionValidationError,
  type EventSessionPayload,
} from '../../services/adminEventSessionsApi'
import type { EventSessionRecord } from '../../services/eventsApi'
import type { DescriptionStyle } from '../../services/settingsApi'
import {
  fetchAdminTicketTypes,
  createAdminTicketType,
  updateAdminTicketType,
  deleteAdminTicketType,
  ValidationError as TicketTypeValidationError,
  type AdminTicketType,
  type TicketTypePayload,
} from '../../services/adminTicketTypesApi'
import {
  fetchAdminCoupons,
  createAdminCoupon,
  updateAdminCoupon,
  ValidationError as CouponValidationError,
  type AdminCoupon,
  type CouponPayload,
} from '../../services/couponsApi'
import {
  createTaskAssignment,
  updateTaskAssignment,
  deleteTaskAssignment,
  ValidationError as TaskAssignmentValidationError,
  type TaskAssignmentRecord,
  type TaskAssignmentPayload,
} from '../../services/adminEventTaskAssignmentsApi'
import { fetchAdminMembers, type AdminMemberSummary } from '../../services/adminMembersApi'
import { formatDateTime, fromDatetimeLocalValue, isIsoDay, toDatetimeLocalValue } from '../../utils/date'
import { groupTicketsByDay, formatTicketDay } from '../../utils/ticketDays'
import { groupSessionsByDay } from '../../utils/scheduleDays'
import { toMinorUnits, fromMinorUnits, formatPrice } from '../../utils/money'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

const { label: ageCategoryLabel } = useLookup('ticket_age_category')
const route = useRoute()
const router = useRouter()
const toast = useToast()

const eventId = computed(() => {
  const id = route.params.id
  return id ? Number(id) : null
})
const isEditing = computed(() => eventId.value !== null)
// Purely informational — editing a past event stays fully allowed (fixing a typo, adding real
// photos after the fact, or correcting the record are all legitimate), and it's architecturally
// safe: ticket/order prices are snapshotted at purchase time (see CLAUDE.md's Payments
// section), so changing a ticket type's price now never rewrites a historical order. This is
// just a heads-up so an admin editing an old event notices before assuming it's upcoming.
const isPastEvent = computed(() => {
  if (!isEditing.value || !form.value.start_datetime) return false
  return new Date(form.value.start_datetime).getTime() < Date.now()
})

const loading = ref(isEditing.value)
const saving = ref(false)
const errors = ref<Record<string, string>>({})
const attribution = ref<{ created_by_email: string | null; updated_by_email: string | null } | null>(null)
const bannerImage = ref<string | null>(null)
const uploadingBanner = ref(false)
const banners = ref<EventBanner[]>([])
const uploadingBannerSlide = ref(false)

// "Ticket payment": two checkboxes over the single stored value (both | qr | app). At least one
// must stay on, so unticking the last one is refused.
// The event's payment methods are stored as a comma-separated list ("qr,app,cash"); the old
// value "both" means "qr,app".
type TicketMethod = 'qr' | 'app' | 'bank' | 'cash' | 'card'
const TICKET_METHODS: TicketMethod[] = ['qr', 'app', 'bank', 'cash', 'card']
const selectedMethods = computed<TicketMethod[]>(() => {
  const v = form.value.ticket_payment_methods
  if (!v || v === 'both') return ['qr', 'app']
  return TICKET_METHODS.filter((m) => v.split(',').includes(m))
})
const acceptsQr = computed(() => selectedMethods.value.includes('qr'))
const acceptsApp = computed(() => selectedMethods.value.includes('app'))
const acceptsBank = computed(() => selectedMethods.value.includes('bank'))
const acceptsCash = computed(() => selectedMethods.value.includes('cash'))
const acceptsCard = computed(() => selectedMethods.value.includes('card'))

function setPaymentMethod(method: TicketMethod, on: boolean, input: HTMLInputElement) {
  const next = new Set(selectedMethods.value)
  if (on) next.add(method)
  else next.delete(method)
  if (next.size === 0) {
    input.checked = true // keep the last method ticked
    return
  }
  form.value.ticket_payment_methods = TICKET_METHODS.filter((m) => next.has(m)).join(',')
}

const form = ref({
  title: '',
  sub_name: '',
  facebook_url: '',
  instagram_url: '',
  max_tickets_per_email: '',
  coupon_max_adult: '',
  coupon_max_child: '',
  description_style: '',
  ticket_payment_methods: 'qr,app',
  ticket_layout: 'sections' as 'sections' | 'tabs',
  cash_note: '',
  slug: '',
  event_type: '',
  short_description: '',
  description: '',
  start_datetime: '',
  end_datetime: '',
  sales_open_at: '',
  sales_close_at: '',
  venue: '',
  address: '',
  capacity: '',
  published: false,
})

function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

// Auto-fills Slug from Title for a NEW event only — never for an existing one, since its slug
// may already be linked/bookmarked elsewhere. Stops auto-filling the moment the admin types
// their own value into Slug: each run only overwrites the field if it still holds exactly what
// the previous run generated (or is still empty), so a manual edit is never clobbered.
let previousAutoSlug = ''

watch(
  () => form.value.title,
  (title) => {
    if (isEditing.value) return
    const nextAutoSlug = slugify(title)
    if (form.value.slug === previousAutoSlug || form.value.slug === '') {
      form.value.slug = nextAutoSlug
    }
    previousAutoSlug = nextAutoSlug
  },
)

const { options: typeOptions } = useLookup('event_type')

const sessions = ref<EventSessionRecord[]>([])

const sessionModalOpen = ref(false)
const editingSession = ref<EventSessionRecord | null>(null)
const savingSession = ref(false)
const sessionErrors = ref<Record<string, string>>({})
const sessionForm = ref({ day_label: '', time: '', title: '', description: '', sort_order: '0' })

const ticketTypes = ref<AdminTicketType[]>([])

const ticketTypeModalOpen = ref(false)
const editingTicketType = ref<AdminTicketType | null>(null)
const savingTicketType = ref(false)
const ticketTypeErrors = ref<Record<string, string>>({})
const ticketTypeForm = ref({
  name: '',
  description: '',
  price: '',
  capacity: '',
  members_only: false,
  age_category: '' as '' | 'adult' | 'child' | 'other',
  coupon_eligible: true,
  sale_start: '',
  sale_end: '',
  valid_on: '',
  sort_order: '0',
})

const ticketGroups = computed(() => groupTicketsByDay(ticketTypes.value))
const scheduleGroups = computed(() => groupSessionsByDay(sessions.value))

// The event's calendar days ("YYYY-MM-DD") from the Start/End fields; empty for a single-day event.
const ALL_DAYS = 'ALL'
const eventDays = computed(() => {
  const first = form.value.start_datetime.slice(0, 10)
  const last = form.value.end_datetime.slice(0, 10)
  if (!first || !last || last <= first) return []
  const days: string[] = []
  const cursor = new Date(`${first}T00:00:00Z`)
  while (cursor.toISOString().slice(0, 10) <= last && days.length < 31) {
    days.push(cursor.toISOString().slice(0, 10))
    cursor.setUTCDate(cursor.getUTCDate() + 1)
  }
  return days
})
const isMultiDay = computed(() => eventDays.value.length > 1)
const validOnOptions = computed(() => [
  ...eventDays.value.map((day) => ({ value: day, label: formatTicketDay(day) })),
  { value: ALL_DAYS, label: 'All days' },
])
const ageCategoryOptions = computed(() => [
  { value: 'other', label: ageCategoryLabel('other') },
  { value: 'adult', label: ageCategoryLabel('adult') },
  { value: 'child', label: ageCategoryLabel('child') },
])

const ticketsOn = moduleEnabled('tickets') // W8-R29: ticket sales, capacity, ticket types and ticket payment belong to the Tickets module
const volunteeringOn = moduleEnabled('volunteering') // W8-R23: volunteer assignments are the Volunteering module's
const couponsOn = moduleEnabled('coupons') // W8-R21: coupons are the Coupons module's: no coupon boxes, section or request without it
const coupons = ref<AdminCoupon[]>([])

const couponModalOpen = ref(false)
const editingCoupon = ref<AdminCoupon | null>(null)
const savingCoupon = ref(false)
const couponErrors = ref<Record<string, string>>({})
const couponForm = ref({
  code: '',
  discount_percent: '',
  is_active: true,
  allowed_ticket_type_ids: [] as number[],
  // Vue auto-applies the .number modifier to a v-model on a native <input type="number">, so
  // this holds '' while blank but a real number once a digit's been typed — never trust it to
  // stay a string (see saveCoupon()'s own handling below).
  max_redemptions: '' as string | number,
})

function toggleCouponAllowedTicketType(ticketTypeId: number) {
  const ids = couponForm.value.allowed_ticket_type_ids
  const index = ids.indexOf(ticketTypeId)
  if (index === -1) {
    ids.push(ticketTypeId)
  } else {
    ids.splice(index, 1)
  }
}

function couponAppliesToNames(coupon: AdminCoupon): { id: number | null; name: string }[] {
  const ids = coupon.allowed_ticket_type_ids ?? []
  const found = ids
    .map((id) => ticketTypes.value.find((t) => t.id === id))
    .filter((t): t is AdminTicketType => !!t)
    .map((t) => ({ id: t.id, name: t.name }))
  return found.length ? found : [{ id: null, name: 'All ticket types' }]
}

// The active coupons that can discount a ticket type: the type must be coupon-eligible, and the coupon either
// has no restriction or lists that type (same rule as checkout).
function couponsForTicketType(ticketType: AdminTicketType): AdminCoupon[] {
  if (!ticketType.coupon_eligible) return []
  return coupons.value.filter((c) => {
    if (!c.is_active) return false
    const allowed = c.allowed_ticket_type_ids ?? []
    return allowed.length === 0 || allowed.includes(ticketType.id)
  })
}

// A ticket name in a coupon's "Applies to" list takes you to that ticket in the Tickets tab and flashes its row.
const highlightedTicketTypeId = ref<number | null>(null)
let highlightTimer: ReturnType<typeof setTimeout> | undefined
async function goToTicketType(id: number) {
  activeTab.value = 'tickets'
  highlightedTicketTypeId.value = id
  await nextTick()
  document.getElementById(`ticket-type-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  clearTimeout(highlightTimer)
  highlightTimer = setTimeout(() => (highlightedTicketTypeId.value = null), 4000)
}

const taskAssignments = ref<TaskAssignmentRecord[]>([])

const { options: taskCategoryOptions, label: taskCategoryLabel } = useLookup('task_category')

const taskAssignmentModalOpen = ref(false)
const editingTaskAssignment = ref<TaskAssignmentRecord | null>(null)
const savingTaskAssignment = ref(false)
const taskAssignmentErrors = ref<Record<string, string>>({})
const taskAssignmentForm = ref({ member_id: '', category: '' })
const volunteerMembers = ref<AdminMemberSummary[]>([])
const loadingVolunteers = ref(false)
const volunteerPickerOpen = ref(false)
const volunteerPickerEl = ref<HTMLElement | null>(null)

const selectedVolunteer = computed(() =>
  volunteerMembers.value.find((m) => String(m.id) === taskAssignmentForm.value.member_id) ?? null,
)

function pickVolunteer(member: AdminMemberSummary) {
  taskAssignmentForm.value.member_id = String(member.id)
  volunteerPickerOpen.value = false
}

function handleVolunteerPickerOutsideClick(event: MouseEvent) {
  if (volunteerPickerOpen.value && volunteerPickerEl.value && !volunteerPickerEl.value.contains(event.target as Node)) {
    volunteerPickerOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleVolunteerPickerOutsideClick))
onUnmounted(() => document.removeEventListener('click', handleVolunteerPickerOutsideClick))

function formattedPrice(ticketType: AdminTicketType): string {
  return formatPrice(ticketType.price)
}

async function loadTicketTypes(): Promise<void> {
  if (!ticketsOn) return
  if (eventId.value === null) return
  try {
    const response = await fetchAdminTicketTypes(eventId.value)
    ticketTypes.value = response.items
  } catch {
    toast.error('Could not load ticket types')
  }
}

async function loadCoupons(): Promise<void> {
  if (!couponsOn) return
  if (eventId.value === null) return
  try {
    const response = await fetchAdminCoupons(eventId.value)
    coupons.value = response.items
  } catch {
    toast.error('Could not load coupons')
  }
}

async function loadEvent(): Promise<AdminEvent | null> {
  if (eventId.value === null) return null
  try {
    const event = await fetchAdminEvent(eventId.value)
    sessions.value = event.sessions
    taskAssignments.value = event.task_assignments
    return event
  } catch {
    toast.error('Could not load this event')
    return null
  }
}

onMounted(async () => {
  if (eventId.value === null) return
  const event = await loadEvent()
  if (event) {
    form.value = {
      title: event.title,
      sub_name: event.sub_name ?? '',
      facebook_url: event.facebook_url ?? '',
      max_tickets_per_email: event.max_tickets_per_email != null ? String(event.max_tickets_per_email) : '',
      coupon_max_adult: event.coupon_max_adult != null ? String(event.coupon_max_adult) : '',
      coupon_max_child: event.coupon_max_child != null ? String(event.coupon_max_child) : '',
      instagram_url: event.instagram_url ?? '',
      description_style: event.description_style ?? '',
      ticket_payment_methods: event.ticket_payment_methods ?? 'qr,app',
      ticket_layout: event.ticket_layout ?? 'sections',
      cash_note: event.cash_note ?? '',
      slug: event.slug,
      event_type: event.event_type,
      short_description: event.short_description ?? '',
      description: event.description ?? '',
      start_datetime: toDatetimeLocalValue(event.start_datetime),
      end_datetime: event.end_datetime ? toDatetimeLocalValue(event.end_datetime) : '',
      sales_open_at: event.sales_open_at ? toDatetimeLocalValue(event.sales_open_at) : '',
      sales_close_at: event.sales_close_at ? toDatetimeLocalValue(event.sales_close_at) : '',
      venue: event.venue ?? '',
      address: event.address ?? '',
      capacity: event.capacity != null ? String(event.capacity) : '',
      published: event.published,
    }
    bannerImage.value = event.banner_image
    banners.value = event.banners ?? []
    attribution.value = {
      created_by_email: event.created_by_email,
      updated_by_email: event.updated_by_email,
    }
  }
  await loadTicketTypes()
  await loadCoupons()
  loading.value = false
})

async function handleBannerSelect(domEvent: Event) {
  if (eventId.value === null) return
  const input = domEvent.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  uploadingBanner.value = true
  try {
    const updated = await uploadEventBanner(eventId.value, file)
    bannerImage.value = updated.banner_image
    toast.success('Banner updated')
  } catch {
    toast.error('Could not upload this banner image')
  } finally {
    uploadingBanner.value = false
    input.value = ''
  }
}

async function removeBanner() {
  if (eventId.value === null) return
  try {
    const updated = await updateAdminEvent(eventId.value, { banner_image: null })
    bannerImage.value = updated.banner_image
    toast.success('Banner removed')
  } catch {
    toast.error('Could not remove this banner')
  }
}

async function handleAddBannerSelect(domEvent: Event) {
  if (eventId.value === null) return
  const input = domEvent.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  uploadingBannerSlide.value = true
  try {
    const updated = await addEventBanner(eventId.value, file)
    banners.value = updated.banners
    toast.success('Banner added')
  } catch {
    toast.error('Could not add this banner image')
  } finally {
    uploadingBannerSlide.value = false
    input.value = ''
  }
}

async function removeBannerSlide(bannerId: number) {
  if (eventId.value === null) return
  try {
    const updated = await deleteEventBanner(eventId.value, bannerId)
    banners.value = updated.banners
    toast.success('Banner removed')
  } catch {
    toast.error('Could not remove this banner')
  }
}

function openAddSession() {
  editingSession.value = null
  sessionErrors.value = {}
  sessionForm.value = { day_label: '', time: '', title: '', description: '', sort_order: String(sessions.value.length) }
  sessionModalOpen.value = true
}

function openEditSession(session: EventSessionRecord) {
  editingSession.value = session
  sessionErrors.value = {}
  sessionForm.value = {
    day_label: isIsoDay(session.day_label) ? session.day_label : '',
    time: session.time,
    title: session.title,
    description: session.description ?? '',
    sort_order: String(session.sort_order),
  }
  sessionModalOpen.value = true
}

async function saveSession() {
  if (eventId.value === null) return
  savingSession.value = true
  sessionErrors.value = {}
  const payload: EventSessionPayload = {
    day_label: sessionForm.value.day_label,
    time: sessionForm.value.time,
    title: sessionForm.value.title,
    description: sessionForm.value.description.trim() || null,
    sort_order: Number(sessionForm.value.sort_order) || 0,
  }
  try {
    if (editingSession.value) {
      await updateEventSession(eventId.value, editingSession.value.id, payload)
      toast.success('Schedule item updated')
    } else {
      await createEventSession(eventId.value, payload)
      toast.success('Schedule item added')
    }
    sessionModalOpen.value = false
    await loadEvent()
  } catch (err) {
    if (err instanceof SessionValidationError) {
      sessionErrors.value = err.errors
    } else {
      toast.error('Could not save this schedule item')
    }
  } finally {
    savingSession.value = false
  }
}

async function removeSession(session: EventSessionRecord) {
  if (eventId.value === null) return
  try {
    await deleteEventSession(eventId.value, session.id)
    toast.success('Schedule item removed')
    await loadEvent()
  } catch {
    toast.error('Could not remove this schedule item')
  }
}

function openAddTicketType() {
  editingTicketType.value = null
  ticketTypeErrors.value = {}
  ticketTypeForm.value = {
    name: '',
    description: '',
    price: '',
    capacity: '',
    members_only: false,
    age_category: '',
    coupon_eligible: true,
    sale_start: '',
    sale_end: '',
    valid_on: '',
    sort_order: String(ticketTypes.value.length),
  }
  ticketTypeModalOpen.value = true
}

function openEditTicketType(ticketType: AdminTicketType) {
  editingTicketType.value = ticketType
  ticketTypeErrors.value = {}
  ticketTypeForm.value = {
    name: ticketType.name,
    description: ticketType.description ?? '',
    price: fromMinorUnits(ticketType.price),
    capacity: ticketType.capacity != null ? String(ticketType.capacity) : '',
    members_only: ticketType.members_only,
    age_category: ticketType.age_category,
    coupon_eligible: ticketType.coupon_eligible,
    sale_start: ticketType.sale_start ? toDatetimeLocalValue(ticketType.sale_start) : '',
    sale_end: ticketType.sale_end ? toDatetimeLocalValue(ticketType.sale_end) : '',
    valid_on: ticketType.valid_on ?? (isMultiDay.value ? ALL_DAYS : ''),
    sort_order: String(ticketType.sort_order),
  }
  ticketTypeModalOpen.value = true
}

async function saveTicketType() {
  if (eventId.value === null) return
  ticketTypeErrors.value = {}
  if (!ticketTypeForm.value.age_category) {
    ticketTypeErrors.value = { age_category: 'Choose an age group.' }
    return
  }
  if (isMultiDay.value && !ticketTypeForm.value.valid_on) {
    ticketTypeErrors.value = { valid_on: 'Choose the day, or All days.' }
    return
  }
  savingTicketType.value = true
  const payload: TicketTypePayload = {
    name: ticketTypeForm.value.name,
    description: ticketTypeForm.value.description.trim() || null,
    price: toMinorUnits(ticketTypeForm.value.price),
    capacity: ticketTypeForm.value.capacity ? Number(ticketTypeForm.value.capacity) : null,
    members_only: ticketTypeForm.value.members_only,
    age_category: ticketTypeForm.value.age_category || undefined,
    coupon_eligible: ticketTypeForm.value.coupon_eligible,
    sale_start: ticketTypeForm.value.sale_start ? fromDatetimeLocalValue(ticketTypeForm.value.sale_start) : null,
    sale_end: ticketTypeForm.value.sale_end ? fromDatetimeLocalValue(ticketTypeForm.value.sale_end) : null,
    ...(isMultiDay.value ? { valid_on: ticketTypeForm.value.valid_on === ALL_DAYS ? null : ticketTypeForm.value.valid_on } : {}),
    sort_order: Number(ticketTypeForm.value.sort_order) || 0,
  }
  try {
    if (editingTicketType.value) {
      await updateAdminTicketType(editingTicketType.value.id, payload)
      toast.success('Ticket type updated')
    } else {
      await createAdminTicketType(eventId.value, payload)
      toast.success('Ticket type added')
    }
    ticketTypeModalOpen.value = false
    await loadTicketTypes()
  } catch (err) {
    if (err instanceof TicketTypeValidationError) {
      ticketTypeErrors.value = err.errors
    } else {
      toast.error('Could not save this ticket type')
    }
  } finally {
    savingTicketType.value = false
  }
}

async function duplicateTicketType(ticketType: AdminTicketType) {
  if (eventId.value === null) return
  try {
    await createAdminTicketType(eventId.value, {
      name: ticketType.name,
      description: ticketType.description,
      price: ticketType.price,
      capacity: ticketType.capacity,
      sale_start: ticketType.sale_start,
      sale_end: ticketType.sale_end,
      valid_on: ticketType.valid_on,
      members_only: ticketType.members_only,
      age_category: ticketType.age_category,
      coupon_eligible: ticketType.coupon_eligible,
      sort_order: Math.max(...ticketTypes.value.map((t) => t.sort_order ?? 0)) + 1,
    })
    toast.success('Ticket type duplicated')
    await loadTicketTypes()
  } catch {
    toast.error('Could not duplicate this ticket type')
  }
}

async function removeTicketType(ticketType: AdminTicketType) {
  try {
    await deleteAdminTicketType(ticketType.id)
    toast.success('Ticket type removed')
    await loadTicketTypes()
  } catch {
    toast.error('Could not remove this ticket type')
  }
}

function openAddCoupon() {
  editingCoupon.value = null
  couponErrors.value = {}
  couponForm.value = {
    code: '',
    discount_percent: '',
    is_active: true,
    allowed_ticket_type_ids: [],
    max_redemptions: '',
  }
  couponModalOpen.value = true
}

function openEditCoupon(coupon: AdminCoupon) {
  editingCoupon.value = coupon
  couponErrors.value = {}
  couponForm.value = {
    code: coupon.code,
    discount_percent: String(coupon.discount_percent),
    is_active: coupon.is_active,
    allowed_ticket_type_ids: [...coupon.allowed_ticket_type_ids],
    max_redemptions: coupon.max_redemptions === null ? '' : String(coupon.max_redemptions),
  }
  couponModalOpen.value = true
}

async function saveCoupon() {
  if (eventId.value === null) return
  savingCoupon.value = true
  couponErrors.value = {}
  const payload: CouponPayload = {
    code: couponForm.value.code,
    discount_percent: Number(couponForm.value.discount_percent),
    is_active: couponForm.value.is_active,
    allowed_ticket_type_ids: couponForm.value.allowed_ticket_type_ids,
    max_redemptions: couponForm.value.max_redemptions === '' ? null : Number(couponForm.value.max_redemptions),
  }
  try {
    if (editingCoupon.value) {
      await updateAdminCoupon(editingCoupon.value.id, payload)
      toast.success('Coupon updated')
    } else {
      await createAdminCoupon(eventId.value, payload)
      toast.success('Coupon added')
    }
    couponModalOpen.value = false
    await loadCoupons()
  } catch (err) {
    if (err instanceof CouponValidationError) {
      couponErrors.value = err.errors
    } else {
      toast.error('Could not save this coupon')
    }
  } finally {
    savingCoupon.value = false
  }
}

async function toggleCouponActive(coupon: AdminCoupon) {
  try {
    await updateAdminCoupon(coupon.id, { is_active: !coupon.is_active })
    await loadCoupons()
  } catch {
    toast.error('Could not update this coupon')
  }
}

function openAddTaskAssignment() {
  editingTaskAssignment.value = null
  taskAssignmentErrors.value = {}
  taskAssignmentForm.value = { member_id: '', category: '' }
  volunteerPickerOpen.value = false
  loadVolunteerMembers()
  taskAssignmentModalOpen.value = true
}

function openEditTaskAssignment(assignment: TaskAssignmentRecord) {
  editingTaskAssignment.value = assignment
  taskAssignmentErrors.value = {}
  taskAssignmentForm.value = { member_id: String(assignment.member_id), category: assignment.category }
  taskAssignmentModalOpen.value = true
}

async function loadVolunteerMembers() {
  loadingVolunteers.value = true
  try {
    const { items } = await fetchAdminMembers('', 'volunteer')
    volunteerMembers.value = items
  } catch {
    toast.error('Could not load registered volunteers')
  } finally {
    loadingVolunteers.value = false
  }
}

async function saveTaskAssignment() {
  if (eventId.value === null) return
  savingTaskAssignment.value = true
  taskAssignmentErrors.value = {}
  const payload: TaskAssignmentPayload = editingTaskAssignment.value
    ? { category: taskAssignmentForm.value.category }
    : {
        member_id: Number(taskAssignmentForm.value.member_id),
        category: taskAssignmentForm.value.category,
      }
  try {
    if (editingTaskAssignment.value) {
      await updateTaskAssignment(eventId.value, editingTaskAssignment.value.id, payload)
      toast.success('Volunteer assignment updated')
    } else {
      await createTaskAssignment(eventId.value, payload)
      toast.success('Volunteer assignment added')
    }
    taskAssignmentModalOpen.value = false
    await loadEvent()
  } catch (err) {
    if (err instanceof TaskAssignmentValidationError) {
      taskAssignmentErrors.value = err.errors
    } else {
      toast.error('Could not save this volunteer assignment')
    }
  } finally {
    savingTaskAssignment.value = false
  }
}

async function removeTaskAssignment(assignment: TaskAssignmentRecord) {
  if (eventId.value === null) return
  try {
    await deleteTaskAssignment(eventId.value, assignment.id)
    toast.success('Volunteer assignment removed')
    await loadEvent()
  } catch {
    toast.error('Could not remove this volunteer assignment')
  }
}

function buildPayload(): EventPayload {
  return {
    title: form.value.title,
    slug: form.value.slug,
    event_type: form.value.event_type,
    sub_name: form.value.sub_name.trim() || null,
    facebook_url: form.value.facebook_url.trim() || null,
    instagram_url: form.value.instagram_url.trim() || null,
    max_tickets_per_email: form.value.max_tickets_per_email ? Number(form.value.max_tickets_per_email) : null,
    coupon_max_adult: form.value.coupon_max_adult ? Number(form.value.coupon_max_adult) : null,
    coupon_max_child: form.value.coupon_max_child ? Number(form.value.coupon_max_child) : null,
    description_style: (form.value.description_style || null) as DescriptionStyle | null,
    ticket_payment_methods: form.value.ticket_payment_methods,
    ticket_layout: form.value.ticket_layout,
    cash_note: form.value.cash_note.trim() || null,
    short_description: form.value.short_description || null,
    description: form.value.description || null,
    start_datetime: form.value.start_datetime
      ? fromDatetimeLocalValue(form.value.start_datetime)
      : undefined,
    end_datetime: form.value.end_datetime ? fromDatetimeLocalValue(form.value.end_datetime) : null,
    sales_open_at: form.value.sales_open_at ? fromDatetimeLocalValue(form.value.sales_open_at) : null,
    sales_close_at: form.value.sales_close_at ? fromDatetimeLocalValue(form.value.sales_close_at) : null,
    venue: form.value.venue || null,
    address: form.value.address || null,
    capacity: form.value.capacity ? Number(form.value.capacity) : null,
    published: form.value.published,
  }
}

const EVENT_TABS: { id: string; label: string; editOnly: boolean; module?: ModuleKey }[] = [
  { id: 'details', label: 'Details', editOnly: false },
  { id: 'media', label: 'Media', editOnly: false },
  { id: 'sales', label: 'Sales', editOnly: false, module: 'tickets' },
  { id: 'schedule', label: 'Schedule', editOnly: true },
  { id: 'tickets', label: 'Tickets', editOnly: true, module: 'tickets' },
  { id: 'coupons', label: 'Coupons', editOnly: true, module: 'coupons' },
  { id: 'volunteers', label: 'Volunteers', editOnly: true, module: 'volunteering' },
]
const activeTab = ref('details')
const visibleTabs = computed(() => EVENT_TABS.filter((t) => (isEditing.value || !t.editOnly) && (!t.module || moduleEnabled(t.module))))
const isCardTab = computed(() => ['details', 'media', 'sales'].includes(activeTab.value))
const SALES_FIELDS = ['ticket_layout', 'sales_open_at', 'sales_close_at', 'max_tickets_per_email', 'coupon_max_adult', 'coupon_max_child', 'ticket_payment_methods', 'cash_note']
const MEDIA_FIELDS = ['banner_image']
// A save error can sit on a tab that is not showing; jump to the first tab that has one.
function showTabWithError(errs: Record<string, string>) {
  const keys = Object.keys(errs)
  if (!keys.length || keys.some((k) => !SALES_FIELDS.includes(k) && !MEDIA_FIELDS.includes(k))) activeTab.value = 'details'
  else activeTab.value = keys.some((k) => SALES_FIELDS.includes(k)) ? 'sales' : 'media'
}

async function save() {
  saving.value = true
  errors.value = {}
  try {
    if (isEditing.value && eventId.value !== null) {
      await updateAdminEvent(eventId.value, buildPayload())
      toast.success('Event updated')
    } else {
      await createAdminEvent(buildPayload())
      toast.success('Event created')
    }
    router.push('/admin/events')
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
      showTabWithError(err.errors)
    } else {
      toast.error('Could not save this event')
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="ds-scope" style="max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div class="ds-heading">
      <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
      <h1 class="ds-display ds-display-s">{{ isEditing ? 'Edit event' : 'New event' }}</h1>
      <p v-if="attribution?.created_by_email || attribution?.updated_by_email" class="ds-meta">
        <span v-if="attribution.created_by_email">Created by {{ attribution.created_by_email }}</span>
        <span v-if="attribution.created_by_email && attribution.updated_by_email"> · </span>
        <span v-if="attribution.updated_by_email">Last edited by {{ attribution.updated_by_email }}</span>
      </p>
    </div>

    <hr class="ds-section-line" />

    <div v-if="isPastEvent" class="ds-alert ds-alert-warning">
      <div>
        <strong class="ds-alert-title">This event has already happened</strong>
        Editing is still allowed — for example to fix a typo or add real photos after the fact — but double-check you're not confusing this with an upcoming event.
      </div>
    </div>

    <nav v-if="!loading" class="ds-tabs event-tabs" aria-label="Event sections" style="flex-wrap: wrap; row-gap: 0">
      <button
        v-for="tab in visibleTabs"
        :key="tab.id"
        type="button"
        class="ds-tab"
        :class="{ 'ds-tab-active': activeTab === tab.id }"
        :aria-current="activeTab === tab.id ? 'page' : undefined"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </nav>

    <BaseLoadingState v-if="loading" label="Loading event…" />
    <div v-else v-show="isCardTab" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
      <div v-show="activeTab === 'details'" class="event-tab-pane" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <label class="ds-field">
          <span class="ds-field-label">Title</span>
          <span class="ds-field-control"><input v-model="form.title" type="text" class="ds-field-input" /></span>
          <span v-if="errors.title" class="ds-field-error-text">{{ errors.title }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Sub-name (optional)</span>
          <span class="ds-field-control"><input v-model="form.sub_name" type="text" placeholder="মহালয়া ২০২৬" class="ds-field-input" /></span>
          <span class="ds-field-hint">Shown under the title on the event page, e.g. a translation of the name.</span>
          <span v-if="errors.sub_name" class="ds-field-error-text">{{ errors.sub_name }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Slug</span>
          <span class="ds-field-control"><input v-model="form.slug" type="text" placeholder="summer-festival-2026" class="ds-field-input" /></span>
          <span v-if="errors.slug" class="ds-field-error-text">{{ errors.slug }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Facebook event link (optional)</span>
          <span class="ds-field-control"><input v-model="form.facebook_url" type="url" placeholder="https://www.facebook.com/events/..." class="ds-field-input" /></span>
          <span v-if="errors.facebook_url" class="ds-field-error-text">{{ errors.facebook_url }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Instagram event link (optional)</span>
          <span class="ds-field-control"><input v-model="form.instagram_url" type="url" placeholder="https://www.instagram.com/..." class="ds-field-input" /></span>
          <span class="ds-field-hint">Shown as icons next to the event actions on the public page.</span>
          <span v-if="errors.instagram_url" class="ds-field-error-text">{{ errors.instagram_url }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Event type</span>
          <BaseSelect v-model="form.event_type" :options="typeOptions" placeholder="Choose a type" />
          <span v-if="errors.event_type" class="ds-field-error-text">{{ errors.event_type }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Start</span>
          <span class="ds-field-control"><input v-model="form.start_datetime" type="datetime-local" class="ds-field-input" /></span>
          <span v-if="errors.start_datetime" class="ds-field-error-text">{{ errors.start_datetime }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">End (optional)</span>
          <span class="ds-field-control"><input v-model="form.end_datetime" type="datetime-local" class="ds-field-input" /></span>
          <span v-if="errors.end_datetime" class="ds-field-error-text">{{ errors.end_datetime }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Venue</span>
          <span class="ds-field-control"><input v-model="form.venue" type="text" class="ds-field-input" /></span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Address</span>
          <span class="ds-field-control"><input v-model="form.address" type="text" class="ds-field-input" /></span>
        </label>

        <label v-if="ticketsOn" class="ds-field">
          <span class="ds-field-label">Capacity</span>
          <span class="ds-field-control"><input v-model="form.capacity" type="number" class="ds-field-input" /></span>
          <span v-if="errors.capacity" class="ds-field-error-text">{{ errors.capacity }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Short description</span>
          <span class="ds-textarea-control">
            <textarea v-model="form.short_description" rows="2" class="ds-textarea"></textarea>
          </span>
        </label>

        <div>
          <RichTextEditor v-model="form.description" label="Description" />
          <span v-if="errors.description" class="ds-field-error-text">{{ errors.description }}</span>
        </div>

        <label class="ds-field">
          <span class="ds-field-label">Description style</span>
          <BaseSelect v-model="form.description_style" :options="[{ value: '', label: 'Site default' }, { value: 'karla', label: 'Karla' }, { value: 'cormorant', label: 'Cormorant Garamond' }, { value: 'source', label: 'Source Serif 4' }]" aria-label="Description style" />
          <span class="ds-field-hint">Overrides the site-wide description style for this event only. Leave on "Site default" unless this event needs its own look.</span>
          <span v-if="errors.description_style" class="ds-field-error-text">{{ errors.description_style }}</span>
        </label>

        <label class="ds-checkbox">
          <input v-model="form.published" type="checkbox" />
          <span class="ds-checkbox-box">✓</span>
          <span class="ds-checkbox-label">Published</span>
        </label>

      </div>
      <div v-show="activeTab === 'media'" class="event-tab-pane" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <div v-if="isEditing" style="display: flex; flex-direction: column; gap: var(--ds-space-2)">
          <span class="ds-field-label">Banner image</span>
          <img
            v-if="bannerImage"
            :src="bannerImage"
            alt="Event banner"
            style="height: 128px; width: 100%; border-radius: var(--ds-radius-md); object-fit: cover"
          />
          <div style="display: flex; align-items: center; gap: var(--ds-space-3)">
            <BaseFileButton size="sm" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" :disabled="uploadingBanner" @change="handleBannerSelect">
              {{ uploadingBanner ? 'Uploading…' : bannerImage ? 'Replace banner' : 'Upload banner' }}
            </BaseFileButton>
            <BaseButton v-if="bannerImage" type="button" variant="ghost" size="sm" @click="removeBanner">
              Remove
            </BaseButton>
          </div>
        </div>
        <div v-if="isEditing" style="display: flex; flex-direction: column; gap: var(--ds-space-2)">
          <span class="ds-field-label">Banners (slider)</span>
          <p class="ds-meta">Add multiple photos to show a left/right slider on the public event page instead of a single banner.</p>
          <div v-if="banners.length" style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap">
            <div v-for="banner in banners" :key="banner.id" style="position: relative; width: 140px; height: 90px">
              <img
                :src="banner.image_url"
                alt="Event banner slide"
                style="width: 100%; height: 100%; border-radius: var(--ds-radius-md); object-fit: cover"
              />
              <BaseIconButton variant="danger" size="sm" label="Remove this banner" style="position: absolute; top: 4px; right: 4px" @click="removeBannerSlide(banner.id)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18" /><path d="M6 6l12 12" /></svg>
              </BaseIconButton>
            </div>
          </div>
          <BaseFileButton size="sm" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" :disabled="uploadingBannerSlide" style="align-self: flex-start" @change="handleAddBannerSelect">
            {{ uploadingBannerSlide ? 'Uploading…' : 'Add banner' }}
          </BaseFileButton>
        </div>

        <p v-else class="ds-meta">Save the event first, then you can upload a banner image.</p>

      </div>
      <div v-if="ticketsOn" v-show="activeTab === 'sales'" class="event-tab-pane" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <label class="ds-field">
          <span class="ds-field-label">Ticket sales open at (optional)</span>
          <span class="ds-field-control"><input v-model="form.sales_open_at" type="datetime-local" class="ds-field-input" aria-label="Ticket sales open at" /></span>
          <span class="ds-field-hint">Start selling tickets at this time. Until then buyers see when sales open. Leave empty to sell right away.</span>
          <span v-if="errors.sales_open_at" class="ds-field-error-text">{{ errors.sales_open_at }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Ticket sales close at (optional)</span>
          <span class="ds-field-control"><input v-model="form.sales_close_at" type="datetime-local" class="ds-field-input" aria-label="Ticket sales close at" /></span>
          <span class="ds-field-hint">Stop selling tickets at this time, for example to order food. The event stays live and listed; buyers see "Ticket sales have closed". Leave empty to sell until the event.</span>
          <span v-if="errors.sales_close_at" class="ds-field-error-text">{{ errors.sales_close_at }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Max tickets per email (per ticket type)</span>
          <span class="ds-field-control"><input v-model="form.max_tickets_per_email" type="number" min="1" placeholder="No limit" class="ds-field-input" /></span>
          <span v-if="errors.max_tickets_per_email" class="ds-field-error-text">{{ errors.max_tickets_per_email }}</span>
        </label>

        <div v-if="couponsOn" style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--ds-space-4)">
          <label class="ds-field">
            <span class="ds-field-label">Coupon order: max adult tickets</span>
            <span class="ds-field-control"><input v-model="form.coupon_max_adult" type="number" min="1" placeholder="No limit" class="ds-field-input" /></span>
            <span v-if="errors.coupon_max_adult" class="ds-field-error-text">{{ errors.coupon_max_adult }}</span>
          </label>
          <label class="ds-field">
            <span class="ds-field-label">Coupon order: max child tickets</span>
            <span class="ds-field-control"><input v-model="form.coupon_max_child" type="number" min="1" placeholder="No limit" class="ds-field-input" /></span>
            <span v-if="errors.coupon_max_child" class="ds-field-error-text">{{ errors.coupon_max_child }}</span>
          </label>
        </div>

        <div class="ds-field">
          <span class="ds-field-label">Ticket payment</span>
          <label class="ds-checkbox" style="align-items: center">
            <input type="checkbox" aria-label="Accept Vipps-QR" :checked="acceptsQr" @change="setPaymentMethod('qr', ($event.target as HTMLInputElement).checked, $event.target as HTMLInputElement)" />
            <span class="ds-checkbox-box">✓</span>
            <span class="ds-meta">Vipps-QR (pay after placing the order)</span>
          </label>
          <label class="ds-checkbox" style="align-items: center">
            <input type="checkbox" aria-label="Accept Vipps-App" :checked="acceptsApp" @change="setPaymentMethod('app', ($event.target as HTMLInputElement).checked, $event.target as HTMLInputElement)" />
            <span class="ds-checkbox-box">✓</span>
            <span class="ds-meta">Vipps-App (+5% convenience fee)</span>
          </label>
          <label class="ds-checkbox" style="align-items: center">
            <input type="checkbox" aria-label="Accept Bank transfer" :checked="acceptsBank" @change="setPaymentMethod('bank', ($event.target as HTMLInputElement).checked, $event.target as HTMLInputElement)" />
            <span class="ds-checkbox-box">✓</span>
            <span class="ds-meta">Bank transfer (account details and reference are shown; an admin confirms the order)</span>
          </label>
          <label class="ds-checkbox" style="align-items: center">
            <input type="checkbox" aria-label="Accept Cash" :checked="acceptsCash" @change="setPaymentMethod('cash', ($event.target as HTMLInputElement).checked, $event.target as HTMLInputElement)" />
            <span class="ds-checkbox-box">✓</span>
            <span class="ds-meta">Cash (pay in person; an admin confirms the order)</span>
          </label>
          <label class="ds-checkbox" style="align-items: center">
            <input type="checkbox" aria-label="Accept Card" :checked="acceptsCard" @change="setPaymentMethod('card', ($event.target as HTMLInputElement).checked, $event.target as HTMLInputElement)" />
            <span class="ds-checkbox-box">✓</span>
            <span class="ds-meta">Card (pay on a Stripe page; confirmed automatically)</span>
          </label>
          <span class="ds-field-hint">At least one must stay on. Vipps-App, Card, Bank transfer and Cash work only once they are switched on in Settings → Payments; until then buyers pay with Vipps-QR.</span>
          <span v-if="errors.ticket_payment_methods" class="ds-field-error-text">{{ errors.ticket_payment_methods }}</span>
        </div>

        <div class="ds-field">
          <span class="ds-field-label">How to show tickets (multi-day events)</span>
          <BaseRadio v-model="form.ticket_layout" name="ticket-layout" value="sections" label="All on one page, grouped by day" description="Every day's tickets are listed on one page under a heading per day. Easiest for people who don't notice tabs." />
          <BaseRadio v-model="form.ticket_layout" name="ticket-layout" value="tabs" label="One day at a time, in tabs" description="A tab per day with the tickets for that day. Shorter page, but the other days are one click away." />
          <span class="ds-field-hint">Only used when ticket types are set to different days (see Tickets → Valid on).</span>
          <span v-if="errors.ticket_layout" class="ds-field-error-text">{{ errors.ticket_layout }}</span>
        </div>

        <label v-if="acceptsCash" class="ds-field">
          <span class="ds-field-label">Cash wording for this event (optional)</span>
          <span class="ds-textarea-control">
            <textarea v-model="form.cash_note" rows="3" maxlength="1000" class="ds-textarea" aria-label="Cash wording"></textarea>
          </span>
          <span class="ds-field-hint">Shown to buyers who choose Cash, e.g. "Your place is not confirmed until you pay. Food is not guaranteed." Leave empty to use the site-wide wording from Settings → Payments.</span>
          <span v-if="errors.cash_note" class="ds-field-error-text">{{ errors.cash_note }}</span>
        </label>

      </div>
      <div v-if="isCardTab" style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton to="/admin/events" variant="ghost" size="md">Cancel</BaseButton>
        <BaseButton type="button" variant="primary" size="md" :disabled="saving" @click="save">
          {{ saving ? 'Saving…' : 'Save' }}
        </BaseButton>
      </div>
    </div>

    <EventRepeatCard v-if="isEditing && !loading && eventId !== null && !squareProfile.eventPass && activeTab === 'details'" :event-id="eventId" />

    <section v-if="isEditing && !loading && activeTab === 'schedule'" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4)">
        <h2 class="ds-title">Schedule</h2>
        <BaseButton type="button" variant="secondary" size="sm" @click="openAddSession">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
          Add schedule item
        </BaseButton>
      </div>

      <div v-if="sessions.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-6)">
        <p class="ds-meta">No schedule items yet.</p>
      </div>
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Programme</th>
                <th></th>
              </tr>
            </thead>
            <tbody v-for="group in scheduleGroups" :key="group.key">
              <tr class="ticket-day-row"><td colspan="3" data-emphasis style="color: var(--ds-terracotta-500); text-transform: uppercase">{{ group.label }}</td></tr>
              <tr v-for="session in group.items" :key="session.id">
                <td>{{ session.time }}</td>
                <td>{{ session.title }}</td>
                <td data-align="right">
                  <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-1)">
                    <BaseIconButton variant="bare" size="sm" :label="`Edit ${session.title}`" @click="openEditSession(session)">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.854.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z" /></svg>
                    </BaseIconButton>
                    <BaseIconButton variant="danger" size="sm" :label="`Remove ${session.title}`" @click="removeSession(session)">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /><line x1="10" x2="10" y1="11" y2="17" /><line x1="14" x2="14" y1="11" y2="17" /></svg>
                    </BaseIconButton>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section v-if="ticketsOn && isEditing && !loading && activeTab === 'tickets'" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4)">
        <h2 class="ds-title">Ticket types</h2>
        <BaseButton type="button" variant="secondary" size="sm" class="add-ticket-type" @click="openAddTicketType">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
          Add ticket type
        </BaseButton>
      </div>

      <div v-if="ticketTypes.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-6)">
        <p class="ds-meta">No ticket types yet.</p>
      </div>
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Price</th>
                <th>Capacity</th>
                <th>Sold</th>
                <th></th>
              </tr>
            </thead>
            <tbody v-for="group in ticketGroups" :key="group.key">
              <tr v-if="group.label" class="ticket-day-row"><td colspan="5" data-emphasis style="color: var(--ds-terracotta-500); text-transform: uppercase">{{ group.label }}</td></tr>
              <tr v-for="ticketType in group.items" :key="ticketType.id" :id="`ticket-type-${ticketType.id}`" :style="highlightedTicketTypeId === ticketType.id ? 'background: color-mix(in srgb, var(--ds-terracotta-500) 22%, transparent)' : ''">
                <td data-emphasis>
                  {{ ticketType.name }}
                  <div v-if="couponsForTicketType(ticketType).length" style="display: flex; flex-wrap: wrap; gap: var(--ds-space-1); margin-top: var(--ds-space-1)">
                    <span v-for="coupon in couponsForTicketType(ticketType)" :key="coupon.id" class="ds-badge ds-badge-accent" :title="`${coupon.code} takes ${coupon.discount_percent}% off this ticket`">{{ coupon.code }} · {{ coupon.discount_percent }}%</span>
                  </div>
                  <div v-if="ticketType.sale_end" class="ds-caption type-sale-note">{{ new Date(ticketType.sale_end) < new Date() ? 'Sales closed' : 'Sales close' }} {{ formatDateTime(ticketType.sale_end) }}</div>
                  <div v-if="ticketType.sale_start && new Date(ticketType.sale_start) > new Date()" class="ds-caption type-sale-note">Opens {{ formatDateTime(ticketType.sale_start) }}</div>
                </td>
                <td style="white-space: nowrap">{{ formattedPrice(ticketType) }}</td>
                <td>{{ ticketType.capacity ?? 'Unlimited' }}</td>
                <td>{{ ticketType.sold }}</td>
                <td data-align="right">
                  <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-1)">
                    <BaseIconButton variant="bare" size="sm" :label="`Edit ${ticketType.name}`" @click="openEditTicketType(ticketType)">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.854.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z" /></svg>
                    </BaseIconButton>
                    <BaseIconButton variant="bare" size="sm" :label="`Duplicate ${ticketType.name}`" @click="duplicateTicketType(ticketType)">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2" /><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" /></svg>
                    </BaseIconButton>
                    <BaseIconButton variant="danger" size="sm" :label="`Remove ${ticketType.name}`" @click="removeTicketType(ticketType)">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /><line x1="10" x2="10" y1="11" y2="17" /><line x1="14" x2="14" y1="11" y2="17" /></svg>
                    </BaseIconButton>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section v-if="couponsOn && isEditing && !loading && activeTab === 'coupons'" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4)">
        <h2 class="ds-title">Coupons</h2>
        <BaseButton type="button" variant="secondary" size="sm" class="add-coupon" @click="openAddCoupon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
          Add coupon
        </BaseButton>
      </div>
      <p class="ds-meta">Applied at checkout to eligible ticket types.</p>

      <div v-if="coupons.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-6)">
        <p class="ds-meta">No coupons yet.</p>
      </div>
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Discount</th>
                <th>Uses</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody v-for="coupon in coupons" :key="coupon.id">
              <tr class="coupon-row">
                <td data-emphasis>{{ coupon.code }}</td>
                <td>{{ coupon.discount_percent }}%</td>
                <td class="ds-meta">
                  {{ coupon.redemption_count }}{{ coupon.max_redemptions !== null ? ` / ${coupon.max_redemptions}` : '' }}
                </td>
                <td>
                  <span class="ds-badge" :class="coupon.is_active ? 'ds-badge-success' : 'ds-badge-neutral'">
                    {{ coupon.is_active ? 'Active' : 'Inactive' }}
                  </span>
                </td>
                <td data-align="right">
                  <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-1)">
                    <BaseIconButton variant="bare" size="sm" :label="`Edit ${coupon.code}`" @click="openEditCoupon(coupon)">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.854.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z" /></svg>
                    </BaseIconButton>
                    <BaseIconButton
                      :variant="coupon.is_active ? 'danger' : 'outline'"
                      size="sm"
                      :label="coupon.is_active ? `Deactivate ${coupon.code}` : `Activate ${coupon.code}`"
                      @click="toggleCouponActive(coupon)"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10" /><line x1="4.93" y1="4.93" x2="19.07" y2="19.07" /></svg>
                    </BaseIconButton>
                  </div>
                </td>
              </tr>
              <tr class="coupon-applies-row">
                <td colspan="5" class="ds-meta" style="padding-top: 0; white-space: normal">
                  <div style="font-weight: 600">Applies to:</div>
                  <div v-for="target in couponAppliesToNames(coupon)" :key="target.name" style="margin-left: 2rem">
                    <a v-if="target.id !== null" :href="`#ticket-type-${target.id}`" class="ds-ref-link" @click.prevent="goToTicketType(target.id)">{{ target.name }}</a>
                    <template v-else>{{ target.name }}</template>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section v-if="volunteeringOn && isEditing && !loading && activeTab === 'volunteers'" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4)">
        <h2 class="ds-title">Volunteer assignments</h2>
        <BaseButton type="button" variant="secondary" size="sm" class="add-task-assignment" @click="openAddTaskAssignment">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><line x1="19" y1="8" x2="19" y2="14" /><line x1="22" y1="11" x2="16" y2="11" /></svg>
          Assign a volunteer
        </BaseButton>
      </div>
      <p class="ds-meta">Internal coordination only — never shown on the public site.</p>

      <div v-if="taskAssignments.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-6)">
        <p class="ds-meta">No volunteers assigned yet.</p>
      </div>
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table">
            <thead>
              <tr>
                <th>Member</th>
                <th>Category</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="assignment in taskAssignments" :key="assignment.id">
                <td data-emphasis>
                  <span style="display: inline-flex; align-items: center; gap: var(--ds-space-3)">
                    <BaseAvatar :name="assignment.member_name" size="sm" />
                    <span>
                      {{ assignment.member_name }}
                      <div v-if="assignment.member_email" class="ds-caption">{{ assignment.member_email }}</div>
                    </span>
                  </span>
                </td>
                <td>{{ taskCategoryLabel(assignment.category) }}</td>
                <td data-align="right">
                  <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-1)">
                    <BaseIconButton variant="bare" size="sm" :label="`Edit ${assignment.member_name}`" @click="openEditTaskAssignment(assignment)">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.854.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z" /></svg>
                    </BaseIconButton>
                    <BaseIconButton variant="danger" size="sm" :label="`Remove ${assignment.member_name}`" @click="removeTaskAssignment(assignment)">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /><line x1="10" x2="10" y1="11" y2="17" /><line x1="14" x2="14" y1="11" y2="17" /></svg>
                    </BaseIconButton>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <BaseModal
      v-if="ticketsOn"
      v-model="ticketTypeModalOpen"
      :title="editingTicketType ? 'Edit ticket type' : 'Add ticket type'"
    >
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <p
          v-if="editingTicketType?.created_by_email || editingTicketType?.updated_by_email"
          class="ds-meta"
        >
          <span v-if="editingTicketType.created_by_email">
            Created by {{ editingTicketType.created_by_email }}
          </span>
          <span v-if="editingTicketType.created_by_email && editingTicketType.updated_by_email"> · </span>
          <span v-if="editingTicketType.updated_by_email">
            Last edited by {{ editingTicketType.updated_by_email }}
          </span>
        </p>
        <label class="ds-field">
          <span class="ds-field-label">Name</span>
          <span class="ds-field-control"><input v-model="ticketTypeForm.name" type="text" placeholder="Adult" class="ds-field-input" /></span>
          <span v-if="ticketTypeErrors.name" class="ds-field-error-text">{{ ticketTypeErrors.name }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Description (shown to buyers)</span>
          <span class="ds-textarea-control">
            <textarea v-model="ticketTypeForm.description" rows="3" placeholder="What's included with this ticket…" class="ds-textarea"></textarea>
          </span>
          <span v-if="ticketTypeErrors.description" class="ds-field-error-text">{{ ticketTypeErrors.description }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Price ({{ squareProfile.currency }})</span>
          <span class="ds-field-control"><input v-model="ticketTypeForm.price" type="number" class="ds-field-input" /></span>
          <span v-if="ticketTypeErrors.price" class="ds-field-error-text">{{ ticketTypeErrors.price }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Capacity (blank = unlimited)</span>
          <span class="ds-field-control"><input v-model="ticketTypeForm.capacity" type="number" class="ds-field-input" /></span>
          <span v-if="ticketTypeErrors.capacity" class="ds-field-error-text">{{ ticketTypeErrors.capacity }}</span>
        </label>
        <label v-if="moduleEnabled('members')" class="ds-checkbox">
          <input v-model="ticketTypeForm.members_only" type="checkbox" />
          <span class="ds-checkbox-box">✓</span>
          <span class="ds-checkbox-label">Members only (label only — not enforced yet)</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Age category</span>
          <BaseSelect v-model="ticketTypeForm.age_category" :options="ageCategoryOptions" placeholder="Choose an age group" />
          <span v-if="couponsOn" class="ds-meta">Used to cap a coupon order at 2 adult + 2 child tickets — see "Coupons" below.</span>
          <span v-if="ticketTypeErrors.age_category" class="ds-field-error-text">{{ ticketTypeErrors.age_category }}</span>
        </label>
        <label v-if="couponsOn" class="ds-checkbox">
          <input v-model="ticketTypeForm.coupon_eligible" type="checkbox" />
          <span class="ds-checkbox-box">✓</span>
          <span class="ds-checkbox-label">Coupon eligible</span>
        </label>
        <span v-if="couponsOn" class="ds-meta" style="margin-top: calc(-1 * var(--ds-space-2))">
          Uncheck for a ticket type a coupon should never discount (e.g. VIP) — a mixed order still
          gets the coupon applied to its other, eligible tickets, with this one charged in full.
        </span>
        <span v-if="couponsOn && ticketTypeErrors.coupon_eligible" class="ds-field-error-text">{{ ticketTypeErrors.coupon_eligible }}</span>
        <label class="ds-field">
          <span class="ds-field-label">Sales open from (optional)</span>
          <span class="ds-field-control"><input v-model="ticketTypeForm.sale_start" type="datetime-local" class="ds-field-input" aria-label="Sales open from" /></span>
          <span v-if="ticketTypeErrors.sale_start" class="ds-field-error-text">{{ ticketTypeErrors.sale_start }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Sales close at (optional)</span>
          <span class="ds-field-control"><input v-model="ticketTypeForm.sale_end" type="datetime-local" class="ds-field-input" aria-label="Sales close at" /></span>
          <span class="ds-field-hint">Closes just this ticket type (e.g. food-included tickets). The event's own "Ticket sales close at" closes everything; the earlier time wins.</span>
          <span v-if="ticketTypeErrors.sale_end" class="ds-field-error-text">{{ ticketTypeErrors.sale_end }}</span>
        </label>
        <label v-if="isMultiDay" class="ds-field">
          <span class="ds-field-label">Valid on</span>
          <BaseSelect v-model="ticketTypeForm.valid_on" :options="validOnOptions" placeholder="Choose a day" aria-label="Valid on" />
          <span class="ds-field-hint">The day this ticket is for — ticket types are sectioned by it. Choose "All days" for a pass that covers the whole event.</span>
          <span v-if="ticketTypeErrors.valid_on" class="ds-field-error-text">{{ ticketTypeErrors.valid_on }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Order</span>
          <span class="ds-field-control"><input v-model="ticketTypeForm.sort_order" type="number" class="ds-field-input" /></span>
        </label>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="ghost" size="md" @click="ticketTypeModalOpen = false">Cancel</BaseButton>
          <BaseButton
            type="button"
            variant="primary"
            size="md"
            class="save-ticket-type"
            :disabled="savingTicketType"
            @click="saveTicketType"
          >
            {{ savingTicketType ? 'Saving…' : 'Save' }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>

    <BaseModal
      v-model="couponModalOpen"
      :title="editingCoupon ? 'Edit coupon' : 'Add coupon'"
    >
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <label class="ds-field">
          <span class="ds-field-label">Code</span>
          <span class="ds-field-control"><input v-model="couponForm.code" type="text" placeholder="SAVE20" class="ds-field-input" style="text-transform: uppercase" /></span>
          <span v-if="couponErrors.code" class="ds-field-error-text">{{ couponErrors.code }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Discount (%)</span>
          <span class="ds-field-control"><input v-model="couponForm.discount_percent" type="number" min="1" max="100" class="ds-field-input" /></span>
          <span class="ds-meta">Up to 100% — a 100% coupon makes the order free and issues tickets immediately, with no payment step.</span>
          <span v-if="couponErrors.discount_percent" class="ds-field-error-text">{{ couponErrors.discount_percent }}</span>
        </label>
        <label class="ds-checkbox">
          <input v-model="couponForm.is_active" type="checkbox" />
          <span class="ds-checkbox-box">✓</span>
          <span class="ds-checkbox-label">Active</span>
        </label>
        <div class="ds-field">
          <span class="ds-field-label">Applies to</span>
          <p v-if="ticketTypes.length === 0" class="ds-meta">Add a ticket type first to restrict this coupon to specific ones.</p>
          <div v-else style="display: flex; flex-wrap: wrap; gap: var(--ds-space-2)">
            <button
              v-for="type in ticketTypes"
              :key="type.id"
              type="button"
              class="ds-tag coupon-ticket-type-pill"
              :class="{ 'ds-tag-selected': couponForm.allowed_ticket_type_ids.includes(type.id) }"
              @click="toggleCouponAllowedTicketType(type.id)"
            >
              {{ type.name }}
            </button>
          </div>
          <span class="ds-meta">
            Select which ticket types this coupon can discount. Leave none selected to allow every
            coupon-eligible ticket type on this event.
          </span>
          <span v-if="couponErrors.allowed_ticket_type_ids" class="ds-field-error-text">{{ couponErrors.allowed_ticket_type_ids }}</span>
        </div>
        <label class="ds-field">
          <span class="ds-field-label">Ticket limit (optional)</span>
          <span class="ds-field-control"><input v-model="couponForm.max_redemptions" type="number" min="1" placeholder="e.g. 50" class="ds-field-input" /></span>
          <span class="ds-meta">
            Maximum number of tickets (not orders — a single order can include several) this
            coupon may be used for. Leave blank for unlimited. Checkout itself is blocked once
            the limit is reached, and the coupon is also automatically deactivated.
          </span>
          <span v-if="editingCoupon" class="ds-meta">Tickets used so far: {{ editingCoupon.redemption_count }}</span>
          <span v-if="couponErrors.max_redemptions" class="ds-field-error-text">{{ couponErrors.max_redemptions }}</span>
        </label>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="ghost" size="md" @click="couponModalOpen = false">Cancel</BaseButton>
          <BaseButton
            type="button"
            variant="primary"
            size="md"
            class="save-coupon"
            :disabled="savingCoupon"
            @click="saveCoupon"
          >
            {{ savingCoupon ? 'Saving…' : 'Save' }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>

    <BaseModal
      v-model="sessionModalOpen"
      :title="editingSession ? 'Edit schedule item' : 'Add schedule item'"
    >
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <label class="ds-field">
          <span class="ds-field-label">Date</span>
          <span class="ds-field-control"><input v-model="sessionForm.day_label" type="date" class="ds-field-input" /></span>
          <span v-if="sessionErrors.day_label" class="ds-field-error-text">{{ sessionErrors.day_label }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Time</span>
          <span class="ds-field-control"><input v-model="sessionForm.time" type="time" class="ds-field-input" /></span>
          <span v-if="sessionErrors.time" class="ds-field-error-text">{{ sessionErrors.time }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Programme</span>
          <span class="ds-field-control"><input v-model="sessionForm.title" type="text" placeholder="Cultural Programme" class="ds-field-input" /></span>
          <span v-if="sessionErrors.title" class="ds-field-error-text">{{ sessionErrors.title }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Description (shown to visitors)</span>
          <span class="ds-textarea-control">
            <textarea v-model="sessionForm.description" rows="3" placeholder="What happens during this item…" class="ds-textarea"></textarea>
          </span>
          <span v-if="sessionErrors.description" class="ds-field-error-text">{{ sessionErrors.description }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Order</span>
          <span class="ds-field-control"><input v-model="sessionForm.sort_order" type="number" class="ds-field-input" /></span>
          <span v-if="sessionErrors.sort_order" class="ds-field-error-text">{{ sessionErrors.sort_order }}</span>
        </label>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="ghost" size="md" @click="sessionModalOpen = false">Cancel</BaseButton>
          <BaseButton type="button" variant="primary" size="md" :disabled="savingSession" @click="saveSession">
            {{ savingSession ? 'Saving…' : 'Save' }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>

    <BaseModal
      v-if="volunteeringOn"
      v-model="taskAssignmentModalOpen"
      :title="editingTaskAssignment ? 'Edit volunteer assignment' : 'Assign a volunteer'"
    >
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <template v-if="!editingTaskAssignment">
          <div class="ds-field">
            <span class="ds-field-label">Volunteer</span>
            <div ref="volunteerPickerEl" style="position: relative">
              <button
                type="button"
                class="ds-select volunteer-picker-trigger"
                style="display: flex; align-items: center; gap: var(--ds-space-2); text-align: left"
                :disabled="loadingVolunteers"
                @click="volunteerPickerOpen = !volunteerPickerOpen"
              >
                <template v-if="selectedVolunteer">
                  <BaseAvatar :name="selectedVolunteer.name" size="sm" />
                  <span>{{ selectedVolunteer.name }}</span>
                </template>
                <span v-else class="ds-meta">{{ loadingVolunteers ? 'Loading volunteers…' : 'Choose a volunteer' }}</span>
              </button>
              <span class="ds-select-caret">▾</span>

              <div v-if="volunteerPickerOpen" class="ds-account-menu-panel" style="top: calc(100% + 4px); left: 0; right: auto; width: 100%; max-height: 240px; overflow-y: auto">
                <div class="ds-account-menu-items">
                  <button
                    v-for="member in volunteerMembers"
                    :key="member.id"
                    type="button"
                    class="ds-account-menu-row"
                    @click="pickVolunteer(member)"
                  >
                    <BaseAvatar :name="member.name" size="sm" />
                    <span class="ds-account-menu-row-label">
                      {{ member.name }}
                      <div class="ds-caption">{{ member.email }}</div>
                    </span>
                  </button>
                </div>
              </div>
            </div>
            <span v-if="!loadingVolunteers && volunteerMembers.length === 0" class="ds-field-hint">
              No registered volunteers yet — promote a member to volunteer at Admin → Volunteers.
            </span>
            <span v-if="taskAssignmentErrors.member_id" class="ds-field-error-text">{{ taskAssignmentErrors.member_id }}</span>
          </div>
        </template>
        <p v-else class="ds-body">
          Member: <strong>{{ editingTaskAssignment.member_name }}</strong>
        </p>
        <label class="ds-field">
          <span class="ds-field-label">Category</span>
          <BaseSelect v-model="taskAssignmentForm.category" :options="taskCategoryOptions" placeholder="Choose a category" />
          <span v-if="taskAssignmentErrors.category" class="ds-field-error-text">{{ taskAssignmentErrors.category }}</span>
        </label>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="ghost" size="md" @click="taskAssignmentModalOpen = false">Cancel</BaseButton>
          <BaseButton
            type="button"
            variant="primary"
            size="md"
            class="save-task-assignment"
            :disabled="savingTaskAssignment"
            @click="saveTaskAssignment"
          >
            {{ savingTaskAssignment ? 'Saving…' : 'Save' }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>
  </div>
</template>
