<script setup lang="ts">
/**
 * Router component for Nova-style declarative fields.
 *
 * Looks at `spec.component` and mounts the matching Vue component
 * from the field registry. Unknown components fall back to the
 * legacy `FormField` widget driven by the old `FieldSchema.type`
 * (passed in as `legacyField`) so admins that still use the
 * string-tuple API keep rendering.
 */
import { computed, defineAsyncComponent } from 'vue'
import type { FieldSpec, FieldSchema } from '@/api/types'
import FormField from '@/components/FormField.vue'

const GeoMapField = defineAsyncComponent(
  () => import('@/components/fields/GeoMapField.vue'),
)

const props = defineProps<{
  spec: FieldSpec
  modelValue: unknown
  /**
   * The matching legacy `FieldSchema` for this column. When the
   * spec's `component` isn't recognised we delegate back to the
   * `FormField` widget so nothing breaks for columns the
   * declarative API hasn't covered yet (e.g. `FileField`,
   * enum-backed selects).
   */
  legacyField?: FieldSchema
  readonly?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: unknown]
}>()

const onUpdate = (value: unknown) => emit('update:modelValue', value)

const isGeoMap = computed(() => props.spec.component === 'GeoMapField')

const effectiveReadonly = computed(
  () => props.readonly || props.spec.readonly,
)
</script>

<template>
  <div class="admin-field">
    <label class="admin-field__label">
      {{ spec.label }}
      <span
        v-if="!spec.nullable && spec.default === null"
        class="admin-field__required"
        aria-hidden="true"
      >*</span>
    </label>

    <GeoMapField
      v-if="isGeoMap"
      :model-value="(modelValue as string | null) ?? null"
      :readonly="effectiveReadonly"
      :options="spec.options"
      @update:model-value="onUpdate"
    />

    <!--
      Everything else still flows through the legacy `FormField`
      widget. This keeps the SPA shipping without rewriting every
      primitive in one go — the declarative API wins for widgets
      it owns (GeoMap, later Markdown / Code / Image), falls back
      for the plumbing ones (Text, Number, Boolean, …).
    -->
    <FormField
      v-else-if="legacyField"
      :field="legacyField"
      :model-value="modelValue"
      :readonly="effectiveReadonly"
      @update:model-value="onUpdate"
    />

    <div v-if="spec.help" class="admin-field__help">
      {{ spec.help }}
    </div>
  </div>
</template>

<style scoped>
.admin-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.admin-field__label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.admin-field__required {
  color: var(--color-danger);
  margin-left: 0.15rem;
}

.admin-field__help {
  font-size: 0.8rem;
  color: var(--text-muted);
}
</style>
