<template>
  <div class="min-vh-100 d-flex align-items-center justify-content-center p-3" style="background: linear-gradient(135deg, #0b2239 0%, #154360 100%)">
    <div class="card shadow-lg border-0" style="max-width: 500px; width: 100%">
      <div class="card-body p-4 p-md-5">
        <div class="text-center mb-4">
          <div class="display-5 text-primary mb-2">
            <i class="bi bi-heart-pulse-fill"></i>
          </div>
          <h3 class="fw-bold mb-1">Hospital BioTrack</h3>
          <p class="text-muted small mb-0">
            Sistema Hospitalario de Gestión de Incidentes y Mantenimiento Médico (CMMS)
          </p>
        </div>

        <div v-if="error" class="alert alert-danger py-2 small">
          <i class="bi bi-exclamation-triangle-fill me-1"></i>{{ error }}
        </div>

        <form @submit.prevent="submitLogin">
          <div class="mb-3">
            <label class="form-label fw-semibold">Correo o Usuario Institucional</label>
            <input
              v-model="email"
              type="text"
              class="form-control form-control-lg"
              placeholder="usuario@biotrack.mx"
              required
            />
          </div>
          <div class="mb-3">
            <label class="form-label fw-semibold">Contraseña</label>
            <input
              v-model="password"
              type="password"
              class="form-control form-control-lg"
              placeholder="••••••••"
              required
            />
          </div>
          <button type="submit" class="btn btn-primary btn-lg w-100 py-3 fw-semibold" :disabled="loading">
            <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>
            Iniciar Sesión
          </button>
        </form>

        <hr class="my-4" />
        <div class="small text-muted mb-2 fw-semibold">
          <i class="bi bi-lightning-charge-fill text-warning me-1"></i>
          Accesos rápidos por perfil (clave: <code>BioTrack2026!</code>):
        </div>
        <div class="d-flex flex-wrap gap-2">
          <button
            v-for="u in demoUsers"
            :key="u.email"
            type="button"
            class="btn btn-outline-secondary btn-sm py-2 px-3"
            @click="quickFill(u.email)"
          >
            {{ u.label }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { defaultHomeForRole } from '../router'

const router = useRouter()
const auth = useAuthStore()

const email = ref('clinico@biotrack.mx')
const password = ref('BioTrack2026!')
const loading = ref(false)
const error = ref('')

const demoUsers = [
  { label: 'Clínico (Piso)', email: 'clinico@biotrack.mx' },
  { label: 'Biomédico (Guardia)', email: 'biomedico@biotrack.mx' },
  { label: 'Jefe Taller', email: 'jefe.taller@biotrack.mx' },
  { label: 'Resp. Área (Firma 2)', email: 'responsable@biotrack.mx' },
  { label: 'Dirección (KPIs)', email: 'direccion@biotrack.mx' },
  { label: 'Auditor COFEPRIS', email: 'auditor@cofepris.mx' },
]

function quickFill(targetEmail) {
  email.value = targetEmail
  password.value = 'BioTrack2026!'
}

async function submitLogin() {
  loading.value = true
  error.value = ''
  try {
    const user = await auth.login(email.value, password.value)
    router.push(defaultHomeForRole(user.role))
  } catch (err) {
    error.value = err.response?.data?.error || 'Error de conexión con el servidor.'
  } finally {
    loading.value = false
  }
}
</script>
