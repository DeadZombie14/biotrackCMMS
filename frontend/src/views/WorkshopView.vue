<template>
  <div class="container-fluid py-4 px-3 px-md-4">
    <!-- Active Critical Alerts Banner (AD-05) -->
    <div v-if="alerts.pendingAlerts.length" class="card border-danger shadow mb-4">
      <div class="card-header bg-danger text-white d-flex flex-wrap justify-content-between align-items-center gap-2">
        <span class="fw-bold">
          <i class="bi bi-bell-fill me-2"></i>ALERTAS PRIORITARIAS DE GUARDIA ({{ alerts.pendingAlerts.length }})
        </span>
        <button class="btn btn-sm btn-outline-light" @click="runEscalationCheck">
          <i class="bi bi-arrow-up-circle me-1"></i>Verificar Escalamientos SLA
        </button>
      </div>
      <div class="list-group list-group-flush">
        <div
          v-for="al in alerts.pendingAlerts"
          :key="al.id"
          class="list-group-item d-flex flex-wrap justify-content-between align-items-center gap-2"
        >
          <div>
            <span :class="['badge me-2', al.status === 'ESCALADO' ? 'bg-dark' : 'bg-danger']">
              {{ al.status }}
            </span>
            <strong>{{ al.message_body }}</strong>
            <div class="small text-muted">
              Guardia asignado: {{ al.assigned_biomedical_name || 'N/A' }} ({{ al.assigned_phone }})
              <span v-if="al.escalated_to_name" class="text-danger fw-bold ms-2">
                → Escalado a Jefe de Taller: {{ al.escalated_to_name }}
              </span>
            </div>
          </div>
          <button class="btn btn-success" @click="alerts.acknowledge(al.id)">
            <i class="bi bi-check2-circle me-1"></i>Acusar Recibo
          </button>
        </div>
      </div>
    </div>

    <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
      <div>
        <h3 class="fw-bold mb-0"><i class="bi bi-wrench-adjustable-circle text-primary me-2"></i>Taller Biomédico</h3>
        <div class="text-muted small">Órdenes de trabajo, notas técnicas, refacciones, calibración y Firma 1</div>
      </div>
      <button class="btn btn-outline-primary" @click="loadOrders">
        <i class="bi bi-arrow-clockwise me-1"></i>Actualizar
      </button>
    </div>

    <!-- Visual Workflow Stepper for Workshop -->
    <div class="card border-0 shadow-sm mb-4">
      <div class="card-body py-2 px-3 small d-flex flex-wrap align-items-center gap-2 text-muted">
        <span class="fw-bold text-dark me-1">Flujo de Taller:</span>
        <span class="badge bg-primary-subtle text-primary-emphasis py-2 px-3">1. Tomar Orden</span>
        <i class="bi bi-chevron-right"></i>
        <span class="badge bg-warning-subtle text-warning-emphasis py-2 px-3">2. Diagnóstico y Refacciones</span>
        <i class="bi bi-chevron-right"></i>
        <span class="badge bg-info-subtle text-info-emphasis py-2 px-3">3. Prueba Metrológica</span>
        <i class="bi bi-chevron-right"></i>
        <span class="badge bg-success-subtle text-success-emphasis py-2 px-3">4. Firma 1 (Folio BioTrack)</span>
      </div>
    </div>

    <div v-if="feedback" class="alert alert-success alert-dismissible fade show">
      {{ feedback }}
      <button type="button" class="btn-close" @click="feedback = ''"></button>
    </div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <!-- Active Work Orders -->
    <div class="row g-3">
      <div v-for="wo in openOrders" :key="wo.id" class="col-12 col-xl-6">
        <div :class="['card shadow-sm h-100', wo.asset?.current_state === 'BLOQUEADO' ? 'border-danger border-2' : 'border-0']">
          <div class="card-header bg-white d-flex flex-wrap justify-content-between align-items-center gap-2">
            <div>
              <span class="fw-bold me-2">OT #{{ wo.id }}</span>
              <span class="badge bg-secondary me-2">{{ wo.service_type }}</span>
              <StatusBadge :state="wo.asset?.current_state" />
            </div>
            <span class="small text-muted fw-semibold">{{ wo.asset?.area_name }}</span>
          </div>
          <div class="card-body">
            <h5 class="fw-bold mb-1">
              {{ wo.asset?.inventory_code }} — {{ wo.asset?.device_type }}
            </h5>
            <div class="small text-muted mb-3">
              {{ wo.asset?.brand }} {{ wo.asset?.model }} · Serie: <code>{{ wo.asset?.serial_number }}</code>
              <span v-if="wo.biomedical_name" class="ms-2">· Técnico: <strong>{{ wo.biomedical_name }}</strong></span>
            </div>

            <!-- Symptom + Clinical Notes Callout -->
            <div class="alert alert-light border py-2 px-3 small mb-3">
              <div>
                <strong>Síntoma reportado:</strong> {{ wo.incident?.symptom_text }}
                <span class="badge bg-danger-subtle text-danger ms-2">{{ wo.incident?.severity }}</span>
              </div>
              <div v-if="wo.incident?.notes" class="mt-2 pt-2 border-top text-dark">
                <i class="bi bi-chat-left-quote-fill text-primary me-1"></i>
                <strong>Mensaje del personal clínico:</strong> {{ wo.incident.notes }}
              </div>
            </div>

            <!-- Prominent Saved Technician Notes & Parts Callout (ALWAYS VISIBLE across all states) -->
            <div
              v-if="wo.technical_diagnosis || wo.parts_used"
              class="alert alert-warning border-warning py-2 px-3 small mb-3"
            >
              <div class="fw-bold text-dark mb-1">
                <i class="bi bi-journal-text me-1"></i>Notas Importantes del Técnico Biomédico:
              </div>
              <div v-if="wo.technical_diagnosis" class="mb-1">
                <strong>Diagnóstico / Mensaje:</strong> {{ wo.technical_diagnosis }}
              </div>
              <div v-if="wo.parts_used">
                <strong>Refacciones:</strong> {{ wo.parts_used }}
                <span v-if="wo.parts_cost" class="badge bg-dark ms-1">${{ wo.parts_cost }} USD</span>
              </div>
            </div>

            <!-- Action: Take Work Order -->
            <div v-if="['REPORTADO', 'BLOQUEADO'].includes(wo.asset?.current_state)" class="d-flex flex-wrap gap-2">
              <button class="btn btn-primary btn-lg flex-fill" @click="takeOrder(wo)">
                <i class="bi bi-hand-index-thumb me-1"></i>Tomar Orden de Trabajo
              </button>
              <button
                v-if="wo.service_type === 'CORRECTIVO'"
                class="btn btn-outline-success btn-lg"
                @click="openFalsePositiveModal(wo)"
              >
                <i class="bi bi-shield-check me-1"></i>Falso Positivo
              </button>
            </div>

            <!-- Action: Diagnosis / Parts / Calibration (Tablet-friendly textareas) -->
            <div v-else-if="['EN_DIAGNOSTICO', 'EN_ESPERA_REFACCION', 'EN_MANTENIMIENTO_PREVENTIVO'].includes(wo.asset?.current_state)">
              <div class="mb-3">
                <label class="form-label small fw-semibold mb-1">
                  Diagnóstico técnico y mensajes importantes para el taller / recepción
                </label>
                <textarea
                  v-model="drafts[wo.id].diagnosis"
                  class="form-control"
                  rows="3"
                  placeholder="Escriba hallazgos importantes, pruebas realizadas o advertencias..."
                ></textarea>
              </div>
              <div class="row g-2 mb-3">
                <div class="col-12 col-sm-8">
                  <label class="form-label small fw-semibold mb-1">Refacciones utilizadas</label>
                  <textarea
                    v-model="drafts[wo.id].parts_used"
                    class="form-control"
                    rows="2"
                    placeholder="Ej. Sensor SpO2 OEM, manguera NIBP"
                  ></textarea>
                </div>
                <div class="col-12 col-sm-4">
                  <label class="form-label small fw-semibold mb-1">Costo ($ USD)</label>
                  <input v-model.number="drafts[wo.id].parts_cost" type="number" min="0" step="10" class="form-control form-control-lg" />
                </div>
              </div>

              <div class="d-flex flex-wrap gap-2">
                <button class="btn btn-outline-dark" @click="updateOrder(wo, null)">
                  <i class="bi bi-save me-1"></i>Guardar Notas
                </button>

                <button
                  v-if="wo.asset?.current_state !== 'EN_ESPERA_REFACCION'"
                  class="btn btn-outline-secondary"
                  @click="updateOrder(wo, 'EN_ESPERA_REFACCION')"
                >
                  <i class="bi bi-hourglass-split me-1"></i>Espera de Refacción
                </button>
                <button
                  v-else
                  class="btn btn-outline-warning"
                  @click="updateOrder(wo, 'EN_DIAGNOSTICO')"
                >
                  <i class="bi bi-box-seam me-1"></i>Pieza Recibida → Diagnóstico
                </button>

                <button class="btn btn-primary" @click="updateOrder(wo, 'EN_CALIBRACION')">
                  <i class="bi bi-sliders me-1"></i>Enviar a Calibración
                </button>

                <button
                  v-if="wo.service_type === 'CORRECTIVO'"
                  class="btn btn-outline-success"
                  @click="openFalsePositiveModal(wo)"
                >
                  <i class="bi bi-shield-check me-1"></i>Falso Positivo (Desestimar)
                </button>

                <button
                  v-if="auth.role === 'JEFE_TALLER' && wo.asset?.current_state === 'EN_DIAGNOSTICO'"
                  class="btn btn-outline-danger ms-auto"
                  @click="updateOrder(wo, 'BAJA_DEFINITIVA')"
                >
                  <i class="bi bi-x-octagon me-1"></i>Baja Definitiva
                </button>
              </div>
            </div>

            <!-- Action: Firma 1 Certification -->
            <div v-else-if="wo.asset?.current_state === 'EN_CALIBRACION'">
              <div class="alert alert-info py-2 small mb-3">
                <i class="bi bi-info-circle me-1"></i>
                Equipo listo para certificación metrológica. Al firmar (Firma 1), se emitirá el Folio Único BioTrack (<code>CAL-YYYY-XXXXX</code>) y pasará a <strong>Pendiente de Recepción (Firma 2)</strong>.
              </div>
              <div class="d-flex flex-wrap gap-2">
                <button class="btn btn-success btn-lg flex-fill fw-semibold" @click="openCertifyModal(wo)">
                  <i class="bi bi-patch-check-fill me-1"></i>Aprobar Calibración y Firmar (Firma 1)
                </button>
                <button
                  v-if="wo.service_type === 'CORRECTIVO'"
                  class="btn btn-outline-success btn-lg"
                  @click="openFalsePositiveModal(wo)"
                >
                  <i class="bi bi-shield-check me-1"></i>Falso Positivo
                </button>
              </div>
            </div>

            <!-- Waiting Firma 2 -->
            <div v-else-if="wo.asset?.current_state === 'CERTIFICADO_PENDIENTE_RECEPCION'" class="alert alert-info py-2 small mb-0">
              <i class="bi bi-pen-fill me-1"></i>
              <strong>Folio {{ wo.certification?.folio_biotrack }}</strong> emitido por {{ wo.certification?.biomedical_signer_name }}.
              <div v-if="wo.certification?.metrological_result" class="mt-1">
                <strong>Resultado metrológico:</strong> {{ wo.certification.metrological_result }}
              </div>
              <div class="mt-1">En espera de confirmación física y <strong>Firma 2</strong> del Responsable del Área Clínica.</div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!openOrders.length" class="col-12">
        <div class="card border-0 shadow-sm p-5 text-center text-muted">
          <i class="bi bi-check2-all display-4 text-success mb-2"></i>
          <h5>No hay órdenes de trabajo activas en este momento</h5>
          <p class="small mb-0">Todas las incidencias están cerradas y el equipamiento está operativo.</p>
        </div>
      </div>
    </div>

    <!-- Firma 1 Re-Auth Modal -->
    <ReauthModal
      :visible="Boolean(certifyTarget)"
      title="Certificación Metrológica — Firma 1 (Biomédico)"
      :description="`Certificando ${certifyTarget?.asset?.inventory_code} (${certifyTarget?.asset?.device_type}). Se generará un Folio Único BioTrack.`"
      confirmLabel="Emitir Folio y Firmar (Firma 1)"
      :loading="signing"
      :error="signError"
      @close="certifyTarget = null"
      @confirm="submitCertify"
    >
      <div class="mb-3">
        <label class="form-label small fw-semibold">Resultado de prueba metrológica *</label>
        <textarea
          v-model="certForm.metrological_result"
          class="form-control"
          rows="3"
          placeholder="Ej. Flujo verificado en patrón CENAM dentro de ±1.0%, alarmas operativas."
          required
        ></textarea>
      </div>
      <div class="mb-2">
        <label class="form-label small fw-semibold">Folio de laboratorio externo (opcional)</label>
        <input
          v-model="certForm.external_lab_folio"
          class="form-control"
          placeholder="Ej. CENAM-EXT-2026-9912"
        />
      </div>
    </ReauthModal>

    <!-- False Positive Dismissal Modal -->
    <div v-if="falsePosTarget" class="modal d-block" tabindex="-1" style="background: rgba(0, 0, 0, 0.55)">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content shadow-lg border-0">
          <div class="modal-header bg-success text-white">
            <h5 class="modal-title fw-bold">
              <i class="bi bi-shield-check me-2"></i>Desestimar como Falso Positivo
            </h5>
            <button type="button" class="btn-close btn-close-white" @click="falsePosTarget = null"></button>
          </div>
          <form @submit.prevent="submitFalsePositive">
            <div class="modal-body p-4">
              <p class="small text-muted mb-3">
                El equipo <strong>{{ falsePosTarget.asset?.inventory_code }}</strong> regresará inmediatamente a
                <strong>OPERATIVO</strong> y esta incidencia quedará excluida de las métricas de falla, MTTR y SLA del hospital.
              </p>
              <label class="form-label fw-semibold small">Justificación técnica / verificación en sitio *</label>
              <textarea
                v-model="falsePosReason"
                class="form-control"
                rows="3"
                placeholder="Ej. Error de uso / cable desconectado. Equipo verificado en sitio 100% operativo."
                required
              ></textarea>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline-secondary btn-lg" @click="falsePosTarget = null">Cancelar</button>
              <button type="submit" class="btn btn-success btn-lg" :disabled="dismissing">
                <span v-if="dismissing" class="spinner-border spinner-border-sm me-1"></span>
                Confirmar Falso Positivo
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useAlertsStore } from '../stores/alerts'
import StatusBadge from '../components/StatusBadge.vue'
import ReauthModal from '../components/ReauthModal.vue'

const auth = useAuthStore()
const alerts = useAlertsStore()

const orders = ref([])
const drafts = reactive({})
const feedback = ref('')
const error = ref('')

const certifyTarget = ref(null)
const certForm = reactive({ metrological_result: '', external_lab_folio: '' })
const signing = ref(false)
const signError = ref('')

const falsePosTarget = ref(null)
const falsePosReason = ref('')
const dismissing = ref(false)

const openOrders = computed(() =>
  orders.value.filter((o) => !['CERRADA', 'BAJA_DEFINITIVA', 'FALSO_POSITIVO'].includes(o.status))
)

async function loadOrders() {
  error.value = ''
  const { data } = await api.get('/work-orders')
  orders.value = data.work_orders || []
  for (const wo of orders.value) {
    drafts[wo.id] = {
      diagnosis: wo.technical_diagnosis || '',
      parts_used: wo.parts_used || '',
      parts_cost: wo.parts_cost || 0,
    }
  }
}

async function takeOrder(wo) {
  try {
    await api.post(`/work-orders/${wo.id}/take`)
    feedback.value = `OT #${wo.id} tomada en diagnóstico.`
    await loadOrders()
    await alerts.fetchAlerts()
  } catch (err) {
    error.value = err.response?.data?.error || 'Error al tomar orden.'
  }
}

async function updateOrder(wo, targetState) {
  error.value = ''
  try {
    const d = drafts[wo.id]
    const payload = {
      technical_diagnosis: d.diagnosis,
      parts_used: d.parts_used,
      parts_cost: d.parts_cost,
    }
    if (targetState) payload.target_state = targetState
    await api.patch(`/work-orders/${wo.id}`, payload)
    feedback.value = targetState
      ? `OT #${wo.id} actualizada a ${targetState}.`
      : `Notas técnicas de la OT #${wo.id} guardadas correctamente.`
    await loadOrders()
  } catch (err) {
    error.value = err.response?.data?.error || 'Transición rechazada por el servidor.'
  }
}

function openCertifyModal(wo) {
  certifyTarget.value = wo
  certForm.metrological_result = 'Prueba metrológica aprobada dentro de tolerancia nominal (NOM-016-SSA3-2012 / NOM-241-SSA1-2025).'
  certForm.external_lab_folio = ''
  signError.value = ''
}

function openFalsePositiveModal(wo) {
  falsePosTarget.value = wo
  falsePosReason.value = 'Falso positivo verificado en sitio (error de operación/conexión). Equipo 100% operativo.'
}

async function submitFalsePositive() {
  dismissing.value = true
  error.value = ''
  try {
    await api.post(`/work-orders/${falsePosTarget.value.id}/false-positive`, {
      reason: falsePosReason.value,
    })
    feedback.value = `OT #${falsePosTarget.value.id} desestimada como Falso Positivo. El equipo regresó a OPERATIVO sin afectar el SLA.`
    falsePosTarget.value = null
    await loadOrders()
    await alerts.fetchAlerts()
  } catch (err) {
    error.value = err.response?.data?.error || 'Error al marcar falso positivo.'
  } finally {
    dismissing.value = false
  }
}

async function submitCertify(password) {
  signing.value = true
  signError.value = ''
  try {
    const { data } = await api.post(`/work-orders/${certifyTarget.value.id}/certify`, {
      reauth_password: password,
      metrological_result: certForm.metrological_result,
      external_lab_folio: certForm.external_lab_folio,
    })
    feedback.value = `Firma 1 registrada. Folio generado: ${data.certification.folio_biotrack}. Ahora requiere Firma 2 del Responsable de Área.`
    certifyTarget.value = null
    await loadOrders()
  } catch (err) {
    signError.value = err.response?.data?.error || 'Firma incorrecta: verifique su contraseña e intente de nuevo.'
  } finally {
    signing.value = false
  }
}

async function runEscalationCheck() {
  const res = await alerts.checkEscalations()
  feedback.value = `Verificación de SLA completada: ${res.escalated_count} alerta(s) escalada(s) al Jefe de Taller.`
}

onMounted(() => {
  loadOrders()
  alerts.fetchAlerts()
})
</script>
