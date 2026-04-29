<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import { useAdminStore } from '@/stores/admin'
import type { ModelSchema, SingleResponse, FieldSpec } from '@/api/types'
import FormField from '@/components/FormField.vue'
import AdminField from '@/components/fields/AdminField.vue'

const props = defineProps<{ slug: string; pk: string }>()

const router = useRouter()
const store = useAdminStore()
const schema = ref<ModelSchema | null>(null)
const formData = ref<Record<string, any>>({})
const saving = ref(false)

const editableFields = computed(() => {
  if (!schema.value) return []
  const form = schema.value.form_fields
  return schema.value.fields.filter((f) => {
    if (f.primary_key) return false
    if (form && !form.includes(f.name)) return false
    return true
  })
})

const readonlyFields = computed(() => {
  if (!schema.value) return []
  return schema.value.fields.filter((f) => f.primary_key)
})

/**
 * Nova-style field specs — when the admin used the
 * ``pylar_admin.fields.*`` API the backend emits a full widget
 * spec per column. Filter down to only the ones that should
 * render on the update form (``visibility.update`` is true), and
 * pair each with its legacy `FieldSchema` so ``AdminField`` can
 * fall back through ``FormField`` for components it doesn't
 * specialise yet.
 */
const updateSpecs = computed<
  { spec: FieldSpec; legacy: ReturnType<typeof lookupLegacy> }[] | null
>(() => {
  if (!schema.value?.field_specs) return null
  return schema.value.field_specs
    .filter((s) => s.visibility.update)
    .map((spec) => ({ spec, legacy: lookupLegacy(spec.name) }))
})

function lookupLegacy(name: string) {
  return schema.value?.fields.find((f) => f.name === name)
}

onMounted(async () => {
  schema.value = await store.fetchSchema(props.slug)
  const res = await api.get<SingleResponse<Record<string, any>>>(
    `/models/${props.slug}/records/${props.pk}`
  )
  formData.value = { ...res.data }
})

async function onSubmit() {
  if (!schema.value) return
  saving.value = true

  try {
    await api.put(`/models/${props.slug}/records/${props.pk}`, formData.value)
    router.push({ name: 'model-list', params: { slug: props.slug } })
  } catch (e: any) {
    store.error = e.body?.error || 'Failed to update record'
  } finally {
    saving.value = false
  }
}

async function onDelete() {
  if (!confirm('Are you sure you want to delete this record?')) return
  await api.del(`/models/${props.slug}/records/${props.pk}`)
  router.push({ name: 'model-list', params: { slug: props.slug } })
}
</script>

<template>
  <div v-if="schema">
    <div class="form-header">
      <h1 class="page-title">Edit {{ schema.label }} #{{ props.pk }}</h1>
      <div class="header-actions">
        <router-link
          :to="{ name: 'model-list', params: { slug: props.slug } }"
          class="btn"
        >
          &larr; Back to list
        </router-link>
        <button class="btn btn-danger" @click="onDelete">Delete</button>
      </div>
    </div>

    <form @submit.prevent="onSubmit" class="record-form">
      <!-- Declarative field path (Nova-style specs) -->
      <template v-if="updateSpecs">
        <AdminField
          v-for="entry in updateSpecs"
          :key="entry.spec.name"
          :spec="entry.spec"
          :legacy-field="entry.legacy"
          v-model="formData[entry.spec.name]"
        />
      </template>

      <!-- Legacy path — string-tuple ``ModelAdmin.list_display`` etc. -->
      <template v-else>
        <FormField
          v-for="field in readonlyFields"
          :key="field.name"
          :field="field"
          v-model="formData[field.name]"
          :readonly="true"
        />
        <FormField
          v-for="field in editableFields"
          :key="field.name"
          :field="field"
          v-model="formData[field.name]"
          :readonly="schema.readonly_fields.includes(field.name)"
        />
      </template>

      <div class="form-actions">
        <button type="submit" class="btn btn-primary" :disabled="saving">
          {{ saving ? 'Saving...' : 'Save Changes' }}
        </button>
      </div>
    </form>
  </div>
  <div v-else class="loading">Loading...</div>
</template>

<style scoped>
.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.record-form {
  max-width: 640px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1.5rem;
}

.form-actions {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}

.loading {
  color: var(--text-muted);
  padding: 2rem;
}
</style>
