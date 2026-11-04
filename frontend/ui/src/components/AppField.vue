<script setup lang="ts">
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from './AppIcon.vue'

// Mirrors design/components/forms/Input.jsx and Select.jsx. Textarea: design v3 `.bx-ta` (screens/ext.css, D.jsx Textarea):
// 84px min, brass focus ring, aria-invalid = danger border, counter at the right, loading skeleton.
export interface FieldOption { value: string; label: string }

const props = withDefaults(defineProps<{
  label: string
  modelValue: string
  as?: 'input' | 'select' | 'textarea'
  type?: string
  options?: FieldOption[]
  hint?: string
  error?: string
  optional?: boolean
  optionalLabel?: string
  leadingIcon?: string
  trailingIcon?: string
  rows?: number
  placeholder?: string
  autocomplete?: string
  disabled?: boolean
  suffix?: string
  max?: number // textarea: character limit shown as "n/max"
  loading?: boolean // textarea: skeleton
}>(), { as: 'input', type: 'text', rows: 5, optionalLabel: 'optional' })

const emit = defineEmits<{ 'update:modelValue': [value: string]; blur: [] }>()

const { t } = useI18n()
const id = useId()
const desc = computed(() => [props.hint && `${id}-h`, props.error && `${id}-e`].filter(Boolean).join(' ') || undefined)
const taDesc = computed(() => `${id}-h`)
const onInput = (e: Event) => emit('update:modelValue', (e.target as HTMLInputElement).value)
</script>

<template>
  <div class="rs-field">
    <label class="rs-label" :for="id">{{ label }}<span v-if="optional" class="rs-opt"> ({{ optionalLabel }})</span></label>
    <template v-if="as === 'textarea'">
      <span v-if="loading" class="bx-sk" style="height: 84px" role="status" :aria-label="t('bx.loading')" />
      <textarea v-else :id="id" class="bx-ta" :value="modelValue" :rows="rows" :placeholder="placeholder" :disabled="disabled" :aria-invalid="error ? true : undefined" :aria-describedby="taDesc" @input="onInput" @blur="emit('blur')" />
      <div :id="taDesc" class="bx-row">
        <span v-if="error" class="bx-err"><AppIcon name="alert" :size="13" />{{ error }}</span>
        <span v-else>{{ hint }}</span>
        <span v-if="max">{{ modelValue.length }}/{{ max }}</span>
      </div>
    </template>
    <template v-else>
      <div v-if="suffix" class="bs-suffix">
        <input :id="id" class="rs-input" :type="type" :value="modelValue" :placeholder="placeholder" :disabled="disabled" :aria-invalid="error ? true : undefined" :aria-describedby="desc" @input="onInput" @blur="emit('blur')">
        <span>{{ suffix }}</span>
      </div>
      <div v-else class="rs-wrap" :class="leadingIcon && 'rs-wrap--lead'">
        <select v-if="as === 'select'" :id="id" class="rs-input" :value="modelValue" :disabled="disabled" :aria-invalid="error ? true : undefined" :aria-describedby="desc" @change="onInput" @blur="emit('blur')">
          <option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
        <input v-else :id="id" class="rs-input" :type="type" :value="modelValue" :placeholder="placeholder" :autocomplete="autocomplete" :disabled="disabled" :aria-invalid="error ? true : undefined" :aria-describedby="desc" @input="onInput" @blur="emit('blur')">
        <AppIcon v-if="as === 'select'" name="chevron-down" />
        <AppIcon v-else-if="as === 'input' && (leadingIcon || trailingIcon)" :name="(leadingIcon || trailingIcon)!" />
      </div>
      <div v-if="hint" :id="`${id}-h`" class="rs-hint">{{ hint }}</div>
      <div v-if="error" :id="`${id}-e`" class="rs-error"><AppIcon name="alert" :size="16" style="margin-top: 3px" />{{ error }}</div>
    </template>
  </div>
</template>
