<template>
  <div v-if="visible" class="modal d-block" tabindex="-1" style="background: rgba(0, 0, 0, 0.55)">
    <div class="modal-dialog modal-dialog-centered">
      <div class="modal-content shadow-lg border-0">
        <div class="modal-header bg-primary text-white">
          <h5 class="modal-title fw-bold">
            <i class="bi bi-shield-check me-2"></i>{{ title }}
          </h5>
          <button type="button" class="btn-close btn-close-white" @click="$emit('close')"></button>
        </div>
        <form @submit.prevent="submit">
          <div class="modal-body p-4">
            <p class="text-muted small mb-3">{{ description }}</p>

            <div
              v-if="error"
              class="alert alert-danger border-danger d-flex align-items-center gap-2 py-2 fw-semibold"
              role="alert"
            >
              <i class="bi bi-x-octagon-fill fs-5"></i>
              <div>{{ error }}</div>
            </div>

            <slot></slot>

            <div class="mb-2 mt-3">
              <label class="form-label fw-semibold">
                <i class="bi bi-key-fill me-1 text-primary"></i>
                Reautenticación obligatoria (Contraseña institucional)
              </label>
              <input
                v-model="password"
                type="password"
                :class="['form-control form-control-lg', error ? 'is-invalid' : '']"
                placeholder="Ingrese su contraseña para firmar digitalmente"
                required
                autofocus
              />
              <div v-if="error" class="invalid-feedback fw-semibold">
                Firma incorrecta. Verifique su contraseña e intente de nuevo.
              </div>
              <div class="form-text">
                Regla AD-06 / NOM-151: Su firma generará una huella criptográfica SHA-256 inmutable.
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-secondary btn-lg" @click="$emit('close')">
              Cancelar
            </button>
            <button type="submit" class="btn btn-primary btn-lg" :disabled="loading">
              <span v-if="loading" class="spinner-border spinner-border-sm me-1"></span>
              <i v-else class="bi bi-pen-fill me-1"></i>
              {{ confirmLabel }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  visible: Boolean,
  title: { type: String, default: 'Confirmación con Firma Digital' },
  description: { type: String, default: '' },
  confirmLabel: { type: String, default: 'Firmar y Confirmar' },
  loading: Boolean,
  error: { type: String, default: '' },
})

const emit = defineEmits(['close', 'confirm'])
const password = ref('')

watch(
  () => props.visible,
  (val) => {
    if (val) password.value = ''
  }
)

watch(
  () => props.error,
  (val) => {
    if (val) password.value = ''
  }
)

function submit() {
  emit('confirm', password.value)
}
</script>
