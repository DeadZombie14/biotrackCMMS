<template>
  <div class="container py-4">
    <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
      <div>
        <h3 class="fw-bold mb-0">
          <i class="bi bi-patch-check-fill text-success me-2"></i>Recepción de Equipos — Doble Validación (Firma 2)
        </h3>
        <div class="text-muted small">
          Ningún equipo regresa a Operativo sin la Firma 1 (Biomédica) + Firma 2 (Responsable del Área Clínica · QA-06).
        </div>
      </div>
      <button class="btn btn-outline-primary" @click="loadPending">
        <i class="bi bi-arrow-clockwise me-1"></i>Actualizar
      </button>
    </div>

    <div v-if="feedback" class="alert alert-success">{{ feedback }}</div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <div class="row g-3">
      <div v-for="wo in pendingOrders" :key="wo.id" class="col-12 col-md-6">
        <div class="card shadow-sm border-info border-2 h-100">
          <div class="card-header bg-info-subtle d-flex justify-content-between align-items-center">
            <span class="fw-bold text-dark">
              <i class="bi bi-file-earmark-check me-1"></i>Folio: {{ wo.certification?.folio_biotrack }}
            </span>
            <StatusBadge :state="wo.asset?.current_state" />
          </div>
          <div class="card-body">
            <h5 class="fw-bold mb-1">{{ wo.asset?.inventory_code }} — {{ wo.asset?.device_type }}</h5>
            <div class="small text-muted mb-3">
              {{ wo.asset?.brand }} {{ wo.asset?.model }} · Área: <strong>{{ wo.asset?.area_name }}</strong>
            </div>

            <div class="alert alert-light border small mb-3">
              <div class="mb-1"><strong>Diagnóstico del técnico:</strong> {{ wo.technical_diagnosis || 'Mantenimiento completado' }}</div>
              <div v-if="wo.parts_used" class="mb-1"><strong>Refacciones:</strong> {{ wo.parts_used }}</div>
              <div class="mb-1"><strong>Resultado metrológico:</strong> {{ wo.certification?.metrological_result }}</div>
              <div class="mb-1"><strong>Firma 1 (Biomédico):</strong> {{ wo.certification?.biomedical_signer_name }}</div>
              <div><strong>Vigencia hasta:</strong> {{ wo.certification?.expiration_date }}</div>
            </div>

            <div v-if="auth.role === 'RESPONSABLE_AREA'" class="d-grid gap-2">
              <button
                class="btn btn-success btn-lg w-100 fw-semibold"
                @click="openReceiveModal(wo)"
              >
                <i class="bi bi-pen-fill me-1"></i>Confirmar Recepción Física (Firma 2) y Emitir QR
              </button>
              <button
                class="btn btn-outline-danger w-100 fw-semibold"
                @click="openRejectModal(wo)"
              >
                <i class="bi bi-arrow-return-left me-1"></i>Rechazar y Devolver a Revisión en Taller
              </button>
            </div>
            <div v-else class="alert alert-warning py-2 small mb-0">
              Inicie sesión como <strong>Responsable de Área</strong> para ejecutar la Firma 2 (Regla de Doble Autorización).
            </div>
          </div>
        </div>
      </div>

      <div v-if="!pendingOrders.length" class="col-12">
        <div class="card border-0 shadow-sm p-5 text-center text-muted">
          <i class="bi bi-clipboard-check display-4 text-success mb-2"></i>
          <h5>No hay equipos pendientes de recepción</h5>
          <p class="small mb-0">Cuando Ingeniería Biomédica complete la Firma 1, los equipos aparecerán aquí para su Firma 2.</p>
        </div>
      </div>
    </div>

    <ReauthModal
      :visible="Boolean(targetOrder)"
      title="Confirmación de Recepción Física — Firma 2"
      :description="`Al firmar, ${targetOrder?.asset?.inventory_code} regresará a estado OPERATIVO y se emitirá la etiqueta física con código QR.`"
      confirmLabel="Firmar Recepción (Firma 2)"
      :loading="signing"
      :error="signError"
      @close="closeModal"
      @confirm="submitFirma2"
    >
      <div class="mb-2">
        <label class="form-label small fw-semibold">Observaciones de recepción física (opcional)</label>
        <textarea
          v-model="receptionNotes"
          class="form-control"
          rows="3"
          placeholder="Ej. Equipo verificado en estación UCI con accesorios completos."
        ></textarea>
      </div>
    </ReauthModal>

    <StickerPrintModal
      :visible="Boolean(printedCert)"
      :certification="printedCert"
      :asset="printedAsset"
      @close="printedCert = null"
    />

    <!-- Reject Reception Modal -->
    <div v-if="rejectTarget" class="modal d-block" tabindex="-1" style="background: rgba(0, 0, 0, 0.55)">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content shadow-lg border-0">
          <div class="modal-header bg-danger text-white">
            <h5 class="modal-title fw-bold">
              <i class="bi bi-arrow-return-left me-2"></i>Rechazar Recepción y Devolver a Taller
            </h5>
            <button type="button" class="btn-close btn-close-white" @click="rejectTarget = null"></button>
          </div>
          <form @submit.prevent="submitReject">
            <div class="modal-body p-4">
              <p class="small text-muted mb-3">
                El equipo <strong>{{ rejectTarget.asset?.inventory_code }}</strong> regresará a
                <strong>EN DIAGNÓSTICO</strong> en Taller Biomédico y su folio preliminar será anulado hasta nueva certificación.
              </p>
              <label class="form-label fw-semibold small">Motivo del rechazo / observaciones para el técnico *</label>
              <textarea
                v-model="rejectReason"
                class="form-control"
                rows="3"
                placeholder="Ej. Faltan accesorios, alarma aún presenta intermitencia o lectura inestable en piso..."
                required
              ></textarea>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline-secondary btn-lg" @click="rejectTarget = null">Cancelar</button>
              <button type="submit" class="btn btn-danger btn-lg" :disabled="rejecting">
                <span v-if="rejecting" class="spinner-border spinner-border-sm me-1"></span>
                Devolver a Revisión
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import StatusBadge from '../components/StatusBadge.vue'
import ReauthModal from '../components/ReauthModal.vue'
import StickerPrintModal from '../components/StickerPrintModal.vue'

const auth = useAuthStore()
const pendingOrders = ref([])
const targetOrder = ref(null)
const receptionNotes = ref('Equipo verificado físicamente en área clínica; accesorios completos.')
const signing = ref(false)
const signError = ref('')
const feedback = ref('')
const error = ref('')

const printedCert = ref(null)
const printedAsset = ref(null)

const rejectTarget = ref(null)
const rejectReason = ref('')
const rejecting = ref(false)

async function loadPending() {
  const { data } = await api.get('/work-orders?pending_reception=true')
  pendingOrders.value = data.work_orders || []
}

function openReceiveModal(wo) {
  targetOrder.value = wo
  signError.value = ''
}

function openRejectModal(wo) {
  rejectTarget.value = wo
  rejectReason.value = ''
}

async function submitReject() {
  rejecting.value = true
  error.value = ''
  try {
    await api.post(`/work-orders/${rejectTarget.value.id}/reject-reception`, {
      rejection_reason: rejectReason.value,
    })
    feedback.value = `Solicitud de ${rejectTarget.value.asset.inventory_code} rechazada y devuelta a Taller Biomédico para revisión.`
    rejectTarget.value = null
    await loadPending()
  } catch (err) {
    error.value = err.response?.data?.error || 'Error al rechazar la recepción.'
  } finally {
    rejecting.value = false
  }
}

function closeModal() {
  targetOrder.value = null
  signError.value = ''
}

async function submitFirma2(password) {
  signing.value = true
  signError.value = ''
  try {
    const { data } = await api.post(`/work-orders/${targetOrder.value.id}/receive`, {
      reauth_password: password,
      reception_notes: receptionNotes.value,
    })
    feedback.value = `Doble validación completada. ${data.work_order.asset.inventory_code} ha regresado a estado OPERATIVO.`
    printedCert.value = data.certification
    printedAsset.value = data.work_order.asset
    targetOrder.value = null
    await loadPending()
  } catch (err) {
    if (err.response?.status === 401) {
      signError.value =
        err.response?.data?.error ||
        'Firma incorrecta: la contraseña institucional ingresada no es válida. Intente nuevamente.'
    } else {
      signError.value = err.response?.data?.error || 'Error al registrar la Firma 2.'
    }
  } finally {
    signing.value = false
  }
}

onMounted(loadPending)
</script>
