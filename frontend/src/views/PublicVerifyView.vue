<template>
  <div class="min-vh-100 d-flex align-items-center justify-content-center bg-light p-3">
    <div class="card shadow border-0" style="max-width: 460px; width: 100%">
      <div class="card-header text-white text-center py-3" :class="headerClass">
        <i class="bi bi-qr-code-scan display-6 d-block mb-1"></i>
        <h5 class="fw-bold mb-0">Verificación Pública de Equipo Médico</h5>
        <div class="small opacity-75">Hospital BioTrack · NOM-241-SSA1-2025 · Transparencia Metrológica</div>
      </div>
      <div class="card-body p-4">
        <div v-if="loading" class="text-center py-4">
          <div class="spinner-border text-primary"></div>
        </div>
        <div v-else-if="error" class="alert alert-danger mb-0">{{ error }}</div>
        <div v-else-if="info">
          <div class="text-center mb-3">
            <span
              :class="['badge fs-5 px-3 py-2', info.is_valid_for_clinical_use ? 'bg-success' : 'bg-danger']"
            >
              <i :class="['bi me-1', info.is_valid_for_clinical_use ? 'bi-check-circle-fill' : 'bi-exclamation-octagon-fill']"></i>
              {{ info.is_valid_for_clinical_use ? 'EQUIPO VIGENTE Y OPERATIVO' : 'NO APTO / VERIFICACIÓN VENCIDA' }}
            </span>
          </div>

          <ul class="list-group list-group-flush small">
            <li class="list-group-item d-flex justify-content-between">
              <span class="text-muted">Folio Institucional</span>
              <strong>{{ info.folio_biotrack }}</strong>
            </li>
            <li class="list-group-item d-flex justify-content-between">
              <span class="text-muted">Unidad Hospitalaria</span>
              <strong class="text-end">{{ info.hospital_name }}</strong>
            </li>
            <li class="list-group-item d-flex justify-content-between">
              <span class="text-muted">Dispositivo</span>
              <strong>{{ info.device_type }}</strong>
            </li>
            <li class="list-group-item d-flex justify-content-between">
              <span class="text-muted">Marca / Modelo</span>
              <span>{{ info.brand }} {{ info.model }}</span>
            </li>
            <li class="list-group-item d-flex justify-content-between">
              <span class="text-muted">Último Servicio</span>
              <strong>{{ info.service_date }}</strong>
            </li>
            <li class="list-group-item d-flex justify-content-between">
              <span class="text-muted">Próxima Vigencia</span>
              <strong>{{ info.expiration_date }}</strong>
            </li>
            <li class="list-group-item d-flex justify-content-between">
              <span class="text-muted">Doble Validación</span>
              <span :class="info.double_signed ? 'text-success fw-bold' : 'text-warning fw-bold'">
                {{ info.double_signed ? 'Completa (Biomédica + Área)' : 'Pendiente' }}
              </span>
            </li>
            <li v-if="info.external_lab_folio" class="list-group-item d-flex justify-content-between">
              <span class="text-muted">Certificado Externo</span>
              <span>{{ info.external_lab_folio }}</span>
            </li>
          </ul>
          <p class="text-muted text-center mt-3 mb-0" style="font-size: 0.72rem">
            Esta consulta pública muestra exclusivamente el estatus de vigencia metrológica sin exponer datos clínicos ni información interna del hospital.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const info = ref(null)
const loading = ref(true)
const error = ref('')

const headerClass = computed(() => {
  if (!info.value) return 'bg-primary'
  return info.value.is_valid_for_clinical_use ? 'bg-success' : 'bg-danger'
})

onMounted(async () => {
  try {
    const { data } = await axios.get(`/api/v1/public/verify/${route.params.token}`)
    info.value = data
  } catch (err) {
    error.value = err.response?.data?.error || 'Código QR no válido.'
  } finally {
    loading.value = false
  }
})
</script>
