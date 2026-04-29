<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import { useAdminStore } from '@/stores/admin'
import type { ModelSchema, FieldSpec } from '@/api/types'
import FormField from '@/components/FormField.vue'
import AdminField from '@/components/fields/AdminField.vue'

const props = defineProps<{ slug: string }>()

const router = useRouter()
const store = useAdminStore()
const schema = ref<ModelSchema | null>(null)
const formData = ref<Record<string, any>>({})
const saving = ref(false)
const errors = ref<Record<string, string>>({})

const editableFields = computed(() => {
  if (!schema.value) return []
  const form = schema.value.form_fields
  return schema.value.fields.filter((f) => {
    if (f.primary_key) return false
    if (form && !form.includes(f.name)) return false
    return true
  })
})

const createSpecs = computed<
  { spec: FieldSpec; legacy: ReturnType<typeof lookupLegacy> }[] | null
>(() => {
  if (!schema.value?.field_specs) return null
  return schema.value.field_specs
    .filter((s) => s.visibility.create)
    .map((spec) => ({ spec, legacy: lookupLegacy(spec.name) }))
})

function lookupLegacy(name: string) {
  return schema.value?.fields.find((f) => f.name === name)
}

onMounted(async () => {
  schema.value = await store.fetchSchema(props.slug)
  if (schema.value) {
    for (const field of editableFields.value) {
      formData.value[field.name] = field.type === 'checkbox' ? false : ''
    }
  }
})

async function onSubmit() {
  if (!schema.value) return
  saving.value = true
  errors.value = {}

  try {
    await api.post(`/models/${props.slug}/records`, formData.value)
    router.push({ name: 'model-list', params: { slug: props.slug } })
  } catch (e: any) {
    if (e.body?.errors) {
      errors.value = e.body.errors
    } else {
      store.error = e.body?.error || 'Failed to create record'
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-if="schema">
    <div class="form-header">
      <h1 class="page-title">Create {{ schema.label }}</h1>
      <router-link
        :to="{ name: 'model-list', params: { slug: props.slug } }"
        class="btn"
      >
        &larr; Back to list
      </router-link>
    </div>

    <form @submit.prevent="onSubmit" class="record-form">
      <template v-if="createSpecs">
        <AdminField
          v-for="entry in createSpecs"
          :key="entry.spec.name"
          :spec="entry.spec"
          :legacy-field="entry.legacy"
          v-model="formData[entry.spec.name]"
        />
      </template>
      <template v-else>
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
          {{ saving ? 'Creating...' : 'Create' }}
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
