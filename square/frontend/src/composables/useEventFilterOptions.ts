import { onMounted, ref } from 'vue'
import { fetchAdminEvents } from '../services/adminEventsApi'

// Options for an events multi-select in an admin toolbar (Orders, Tickets); give the control
// all-label="All events". The value is the event id as a string. A failed load leaves it empty.
export function useEventFilterOptions() {
  const eventOptions = ref<{ value: string; label: string }[]>([])

  onMounted(async () => {
    try {
      const { items } = await fetchAdminEvents(1, 50)
      eventOptions.value = items.map((event) => ({ value: String(event.id), label: event.title }))
    } catch {
      /* leave the options empty */
    }
  })

  return { eventOptions }
}
