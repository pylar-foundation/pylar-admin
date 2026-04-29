<script setup lang="ts">
import { computed } from 'vue'
import type { FieldSchema } from '@/api/types'

const props = defineProps<{
  field: FieldSchema
  modelValue: any
  readonly: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: any]
}>()

const inputType = computed(() => {
  const map: Record<string, string> = {
    text: 'text',
    number: 'number',
    checkbox: 'checkbox',
    date: 'date',
    time: 'time',
    'datetime-local': 'datetime-local',
    file: 'file',
  }
  return map[props.field.type] || 'text'
})

function onInput(e: Event) {
  const target = e.target as HTMLInputElement
  if (props.field.type === 'checkbox') {
    emit('update:modelValue', target.checked)
  } else if (props.field.type === 'number') {
    emit('update:modelValue', target.value === '' ? null : Number(target.value))
  } else {
    emit('update:modelValue', target.value)
  }
}
</script>

<template>
  <div class="form-group">
    <label class="form-label">
      {{ field.label }}
      <span v-if="!field.nullable && !field.has_default" class="required">*</span>
    </label>

    <!-- Select for enum/choices -->
    <select
      v-if="field.type === 'select' && field.choices"
      :value="modelValue"
      @change="onInput"
      :disabled="readonly"
      class="form-control"
    >
      <option value="">-- select --</option>
      <option v-for="[val, label] in field.choices" :key="val" :value="val">
        {{ label }}
      </option>
    </select>

    <!-- Textarea -->
    <textarea
      v-else-if="field.type === 'textarea' || field.type === 'json'"
      :value="field.type === 'json' ? JSON.stringify(modelValue, null, 2) : modelValue"
      @input="onInput"
      :readonly="readonly"
      class="form-control form-textarea"
      rows="4"
    />

    <!-- Checkbox -->
    <input
      v-else-if="field.type === 'checkbox'"
      type="checkbox"
      :checked="modelValue"
      @change="onInput"
      :disabled="readonly"
      class="form-checkbox"
    />

    <!-- Standard input -->
    <input
      v-else
      :type="inputType"
      :value="modelValue"
      @input="onInput"
      :readonly="readonly"
      class="form-control"
      v-bind="field.attrs"
    />
  </div>
</template>

<style scoped>
.form-group {
  margin-bottom: 1rem;
}

.form-label {
  display: block;
  margin-bottom: 0.25rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: capitalize;
}

.required {
  color: var(--color-danger);
}

.form-control {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 0.875rem;
  font-family: inherit;
}

.form-control:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-alpha);
}

.form-control:read-only {
  background: var(--bg-sidebar);
  cursor: not-allowed;
}

.form-textarea {
  resize: vertical;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.form-checkbox {
  width: 1.25rem;
  height: 1.25rem;
  accent-color: var(--accent);
}
</style>
