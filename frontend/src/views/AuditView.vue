<template>
  <div class="container py-4">
    <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-3">
      <div>
        <h3 class="fw-bold mb-1">
          <i class="bi bi-shield-lock-fill text-primary me-2"></i>Bitácora Inalterable y Verificador COFEPRIS (Solo Lectura)
        </h3>
        <p class="text-muted small mb-0">
          Línea del tiempo cronológica verificable criptográficamente en cadena SHA-256 (NOM-016-SSA3-2012 · NOM-240-SSA1-2012 · NOM-241-SSA1-2025 · NOM-151-SCFI-2016).
        </p>
      </div>
    </div>

    <!-- Giant Prominent Print Full Report Button at the Top of COFEPRIS View -->
    <div class="d-grid mb-4 no-print">
      <button
        type="button"
        class="btn btn-primary btn-lg py-3 fs-4 fw-bold shadow"
        :disabled="!dossier"
        @click="printFullReport"
      >
        <i class="bi bi-printer-fill me-2"></i>Imprimir reporte completo
      </button>
    </div>

    <!-- Search Bar -->
    <div class="card border-0 shadow-sm mb-4">
      <div class="card-body">
        <form class="row g-2 align-items-center" @submit.prevent="searchDossier">
          <div class="col-12 col-md-7">
            <input
              v-model="query"
              class="form-control form-control-lg"
              placeholder="Buscar por N° de serie o código (ej. ZOL-RSP-2022-001, QRF-ANE-01)"
              required
            />
          </div>
          <div class="col-12 col-md-5 d-flex flex-wrap gap-2">
            <button type="submit" class="btn btn-primary btn-lg" :disabled="loading">
              <i class="bi bi-search me-1"></i>Consultar
            </button>
            <button type="button" class="btn btn-outline-secondary" @click="quickLoad('ZOL-RSP-2022-001')">
              Desfibrilador
            </button>
            <button type="button" class="btn btn-outline-secondary" @click="quickLoad('QRF-ANE-01')">
              Anestesia
            </button>
            <button type="button" class="btn btn-outline-secondary" @click="quickLoad('UCI-BOM-01')">
              Bomba UCI
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <div v-if="dossier">
      <!-- Cryptographic Integrity Banner -->
      <div
        :class="[
          'alert shadow-sm d-flex flex-wrap justify-content-between align-items-center gap-2',
          dossier.integrity.valid ? 'alert-success' : 'alert-danger',
        ]"
      >
        <div>
          <h5 class="fw-bold mb-1">
            <i :class="['bi me-2', dossier.integrity.valid ? 'bi-patch-check-fill' : 'bi-exclamation-octagon-fill']"></i>
            {{ dossier.integrity.valid ? 'CADENA CRIPTOGRÁFICA SHA-256 ÍNTEGRA (SIN ALTERACIONES)' : 'ALERTA: INTEGRIDAD COMPROMETIDA' }}
          </h5>
          <div class="small">{{ dossier.integrity.reason }}</div>
          <div class="hash-mono mt-1 text-dark">
            <strong>Head Hash:</strong> {{ dossier.integrity.head_hash }}
          </div>
        </div>
        <button class="btn btn-outline-dark" @click="reverify">
          <i class="bi bi-shield-check me-1"></i>Re-verificar SHA-256
        </button>
      </div>

      <!-- Asset Header -->
      <div class="card border-0 shadow-sm mb-4">
        <div class="card-body d-flex flex-wrap justify-content-between align-items-center gap-2">
          <div>
            <h5 class="fw-bold mb-0">{{ dossier.asset.inventory_code }} — {{ dossier.asset.device_type }}</h5>
            <div class="small text-muted">
              {{ dossier.asset.brand }} {{ dossier.asset.model }} · Serie: <code>{{ dossier.asset.serial_number }}</code> · Área: {{ dossier.asset.area_name }}
            </div>
          </div>
          <StatusBadge :state="dossier.asset.current_state" />
        </div>
      </div>

      <!-- SmartArt-style Interactive Timeline -->
      <div class="card border-0 shadow-sm mb-4">
        <div class="card-header bg-white d-flex flex-wrap justify-content-between align-items-center py-3">
          <div>
            <span class="fw-bold fs-5">
              <i class="bi bi-diagram-3-fill text-primary me-2"></i>Línea del Tiempo de Acciones ({{ dossier.audit_events.length }})
            </span>
            <div class="small text-muted">Toque cualquier paso en la línea del tiempo para ver su detalle completo, usuario, fecha y firma SHA-256.</div>
          </div>
        </div>

        <div class="card-body">
          <div v-if="!dossier.audit_events.length" class="text-center text-muted py-4">
            <i class="bi bi-clock-history display-6 d-block mb-2"></i>
            Este equipo aún no tiene eventos de mantenimiento o incidencias registrados en la bitácora COFEPRIS.
          </div>

          <div v-else>
            <!-- Horizontal Scrollable SmartArt Process Flow -->
            <div class="smartart-track d-flex align-items-stretch gap-2 pb-3 mb-4 overflow-auto">
              <template v-for="(ev, idx) in dossier.audit_events" :key="ev.id">
                <button
                  type="button"
                  @click="selectEvent(ev)"
                  :class="[
                    'smartart-node text-start border-2 rounded-4 p-3 flex-shrink-0',
                    eventMeta(ev.event_type).cardClass,
                    selectedEvent?.id === ev.id ? 'smartart-node-active shadow' : 'bg-white'
                  ]"
                >
                  <div class="d-flex justify-content-between align-items-center mb-2">
                    <span :class="['badge rounded-pill', eventMeta(ev.event_type).badgeClass]">
                      Paso {{ idx + 1 }}
                    </span>
                    <i :class="['bi fs-5', eventMeta(ev.event_type).icon, eventMeta(ev.event_type).textClass]"></i>
                  </div>
                  <div class="fw-bold text-dark small mb-1">{{ eventMeta(ev.event_type).label }}</div>
                  <div class="text-muted" style="font-size: 0.74rem">
                    <i class="bi bi-person-fill me-1"></i>{{ ev.actor_name }}
                  </div>
                  <div class="text-muted mt-1" style="font-size: 0.72rem">
                    <i class="bi bi-clock me-1"></i>{{ formatTimestamp(ev.timestamp_utc) }}
                  </div>
                </button>

                <div
                  v-if="idx < dossier.audit_events.length - 1"
                  class="d-flex align-items-center text-primary fs-4 px-1 flex-shrink-0"
                >
                  <i class="bi bi-arrow-right-circle-fill opacity-75"></i>
                </div>
              </template>
            </div>

            <!-- Selected Node Detailed Inspector Card -->
            <div v-if="selectedEvent" class="card border-primary border-2 shadow-sm bg-light-subtle">
              <div class="card-header bg-primary text-white d-flex flex-wrap justify-content-between align-items-center gap-2 py-3">
                <div class="d-flex align-items-center gap-2">
                  <i :class="['bi fs-4', eventMeta(selectedEvent.event_type).icon]"></i>
                  <div>
                    <div class="fw-bold fs-5">{{ eventMeta(selectedEvent.event_type).label }}</div>
                    <div class="small opacity-75">Evento #{{ selectedEvent.id }} · Código técnico: {{ selectedEvent.event_type }}</div>
                  </div>
                </div>
                <span class="badge bg-light text-dark fs-6">
                  <i class="bi bi-calendar-check me-1"></i>{{ formatTimestamp(selectedEvent.timestamp_utc) }} (UTC)
                </span>
              </div>

              <div class="card-body p-4">
                <div class="row g-3 mb-4">
                  <div class="col-12 col-md-6">
                    <div class="p-3 bg-white rounded border h-100">
                      <div class="small text-muted text-uppercase fw-semibold mb-1">Usuario Responsable</div>
                      <div class="fw-bold fs-6 text-dark">
                        <i class="bi bi-person-badge-fill text-primary me-1"></i>{{ selectedEvent.actor_name }}
                      </div>
                      <span class="badge bg-secondary mt-1">{{ selectedEvent.actor_role }}</span>
                    </div>
                  </div>
                  <div class="col-12 col-md-6">
                    <div class="p-3 bg-white rounded border h-100">
                      <div class="small text-muted text-uppercase fw-semibold mb-1">Sello Temporal Confiable</div>
                      <div class="fw-bold fs-6 text-dark">
                        <i class="bi bi-clock-history text-primary me-1"></i>{{ formatTimestamp(selectedEvent.timestamp_utc) }}
                      </div>
                      <div class="small text-muted">ISO UTC: <code>{{ selectedEvent.timestamp_utc }}Z</code></div>
                    </div>
                  </div>
                </div>

                <!-- Parsed Payload Table -->
                <h6 class="fw-bold mb-2">
                  <i class="bi bi-card-checklist text-primary me-1"></i>Detalles de la Acción (Payload)
                </h6>
                <div class="table-responsive bg-white rounded border mb-3">
                  <table class="table table-sm align-middle mb-0">
                    <tbody>
                      <tr v-for="(val, key) in parsedPayload(selectedEvent.payload_json)" :key="key">
                        <th class="bg-light text-muted small ps-3" style="width: 34%">{{ formatPayloadKey(key) }}</th>
                        <td class="ps-3 small fw-semibold text-break">{{ formatPayloadVal(val) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <!-- Cryptographic Hash Proof -->
                <div class="p-3 bg-white rounded border">
                  <div class="small fw-bold text-success mb-1">
                    <i class="bi bi-link-45deg me-1"></i>Prueba de Integridad Criptográfica (SHA-256)
                  </div>
                  <div class="hash-mono text-muted mb-1">
                    <strong>Hash Previo:</strong> {{ selectedEvent.prev_hash }}
                  </div>
                  <div class="hash-mono text-success">
                    <strong>Hash Registro:</strong> {{ selectedEvent.record_hash }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Certifications Summary Table -->
      <div v-if="dossier.certifications.length" class="card border-0 shadow-sm">
        <div class="card-header bg-white fw-bold">Certificaciones Metrológicas y Doble Firma</div>
        <div class="table-responsive">
          <table class="table table-sm align-middle mb-0">
            <thead class="table-light">
              <tr>
                <th>Folio BioTrack</th>
                <th>Lab Externo</th>
                <th>Fecha Servicio</th>
                <th>Vigencia</th>
                <th>Firma 1 (Biomédico)</th>
                <th>Firma 2 (Área)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in dossier.certifications" :key="c.id">
                <td class="fw-bold">{{ c.folio_biotrack }}</td>
                <td class="small">{{ c.external_lab_folio || '—' }}</td>
                <td class="small">{{ c.service_date }}</td>
                <td class="small">{{ c.expiration_date }}</td>
                <td class="small">{{ c.biomedical_signer_name }}</td>
                <td class="small">{{ c.area_receiver_name || 'Pendiente' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Formal Printable Full Report in Clean Readable Tables (visible when printing) -->
      <div id="printable-audit-report" class="d-none d-print-block mt-4">
        <div class="border-bottom border-2 border-dark pb-2 mb-3">
          <h3 class="fw-bold mb-1">Hospital BioTrack — Reporte Completo de Auditoría COFEPRIS</h3>
          <div class="small">
            <strong>Marco Normativo:</strong> NOM-016-SSA3-2012 · NOM-240-SSA1-2012 · NOM-241-SSA1-2025 · NOM-151-SCFI-2016
          </div>
          <div class="small">
            <strong>Integridad SHA-256:</strong>
            {{ dossier.integrity.valid ? 'ÍNTEGRA (SIN ALTERACIONES)' : 'COMPROMETIDA' }}
            · <strong>Head Hash:</strong> <code>{{ dossier.integrity.head_hash }}</code>
          </div>
        </div>

        <h5 class="fw-bold mt-3 mb-2">1. Ficha Técnica del Dispositivo Médico</h5>
        <table class="table table-bordered table-sm small mb-3">
          <tbody>
            <tr>
              <th style="width: 22%">Código Inventario</th>
              <td style="width: 28%">{{ dossier.asset.inventory_code }}</td>
              <th style="width: 22%">Número de Serie</th>
              <td style="width: 28%">{{ dossier.asset.serial_number }}</td>
            </tr>
            <tr>
              <th>Dispositivo</th>
              <td>{{ dossier.asset.device_type }}</td>
              <th>Marca / Modelo</th>
              <td>{{ dossier.asset.brand }} {{ dossier.asset.model }}</td>
            </tr>
            <tr>
              <th>Área Clínica</th>
              <td>{{ dossier.asset.area_name }}</td>
              <th>Estado Actual</th>
              <td>{{ dossier.asset.current_state }}</td>
            </tr>
            <tr>
              <th>Último Servicio</th>
              <td>{{ dossier.asset.last_service_date || '—' }}</td>
              <th>Próximo Preventivo</th>
              <td>{{ dossier.asset.next_preventive_date || '—' }}</td>
            </tr>
          </tbody>
        </table>

        <h5 class="fw-bold mt-3 mb-2">2. Certificaciones Metrológicas y Doble Validación</h5>
        <table class="table table-bordered table-sm small mb-3">
          <thead>
            <tr>
              <th>Folio BioTrack</th>
              <th>Lab Externo</th>
              <th>Servicio</th>
              <th>Vigencia</th>
              <th>Resultado Metrológico</th>
              <th>Firma 1 (Biomédico)</th>
              <th>Firma 2 (Área)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in dossier.certifications" :key="'pcert-' + c.id">
              <td>{{ c.folio_biotrack }}</td>
              <td>{{ c.external_lab_folio || '—' }}</td>
              <td>{{ c.service_date }}</td>
              <td>{{ c.expiration_date }}</td>
              <td>{{ c.metrological_result }}</td>
              <td>{{ c.biomedical_signer_name }}</td>
              <td>{{ c.area_receiver_name || 'Pendiente' }}</td>
            </tr>
            <tr v-if="!dossier.certifications.length">
              <td colspan="7" class="text-center">Sin certificaciones registradas.</td>
            </tr>
          </tbody>
        </table>

        <h5 class="fw-bold mt-3 mb-2">3. Bitácora Cronológica Inalterable (Cadena SHA-256)</h5>
        <table class="table table-bordered table-sm small">
          <thead>
            <tr>
              <th>#</th>
              <th>Fecha/Hora (UTC)</th>
              <th>Acción</th>
              <th>Usuario (Rol)</th>
              <th>Detalles / Payload</th>
              <th>Hash SHA-256</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(ev, idx) in dossier.audit_events" :key="'pev-' + ev.id">
              <td>{{ idx + 1 }}</td>
              <td>{{ formatTimestamp(ev.timestamp_utc) }}</td>
              <td><strong>{{ eventMeta(ev.event_type).label }}</strong></td>
              <td>{{ ev.actor_name }} ({{ ev.actor_role }})</td>
              <td>
                <div v-for="(val, k) in parsedPayload(ev.payload_json)" :key="k">
                  <strong>{{ formatPayloadKey(k) }}:</strong> {{ formatPayloadVal(val) }}
                </div>
              </td>
              <td class="hash-mono">{{ ev.record_hash }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../services/api'
import StatusBadge from '../components/StatusBadge.vue'

const query = ref('ZOL-RSP-2022-001')
const dossier = ref(null)
const selectedEvent = ref(null)
const loading = ref(false)
const error = ref('')

function eventMeta(type) {
  const map = {
    INCIDENT_REPORTED: {
      label: 'Reporte de Incidencia',
      icon: 'bi-exclamation-triangle-fill',
      badgeClass: 'bg-warning text-dark',
      cardClass: 'border-warning',
      textClass: 'text-warning',
    },
    ASSET_BLOCKED_FAILSAFE: {
      label: 'Bloqueo Fail-Safe',
      icon: 'bi-slash-circle-fill',
      badgeClass: 'bg-danger',
      cardClass: 'border-danger',
      textClass: 'text-danger',
    },
    ALERT_DISPATCHED_ONCALL: {
      label: 'Aviso a Guardia',
      icon: 'bi-bell-fill',
      badgeClass: 'bg-danger',
      cardClass: 'border-danger',
      textClass: 'text-danger',
    },
    ALERT_ACKNOWLEDGED: {
      label: 'Acuse de Guardia',
      icon: 'bi-check2-circle',
      badgeClass: 'bg-info text-dark',
      cardClass: 'border-info',
      textClass: 'text-info',
    },
    ALERT_ESCALATED_CHIEF: {
      label: 'Escalamiento a Jefe',
      icon: 'bi-arrow-up-circle-fill',
      badgeClass: 'bg-dark',
      cardClass: 'border-dark',
      textClass: 'text-dark',
    },
    WORK_ORDER_TAKEN: {
      label: 'Orden Tomada',
      icon: 'bi-wrench-adjustable',
      badgeClass: 'bg-primary',
      cardClass: 'border-primary',
      textClass: 'text-primary',
    },
    WORK_ORDER_EN_CALIBRACION: {
      label: 'Enviado a Calibración',
      icon: 'bi-sliders',
      badgeClass: 'bg-primary',
      cardClass: 'border-primary',
      textClass: 'text-primary',
    },
    CERTIFICATION_FIRMA1_BIOMEDICAL: {
      label: 'Certificación (Firma 1)',
      icon: 'bi-patch-check-fill',
      badgeClass: 'bg-info text-dark',
      cardClass: 'border-info',
      textClass: 'text-info',
    },
    RECEPTION_FIRMA2_AREA_OPERATIVE: {
      label: 'Recepción Operativa (Firma 2)',
      icon: 'bi-check-circle-fill',
      badgeClass: 'bg-success',
      cardClass: 'border-success',
      textClass: 'text-success',
    },
    PREVENTIVE_STARTED: {
      label: 'Preventivo Iniciado',
      icon: 'bi-calendar-check-fill',
      badgeClass: 'bg-info text-dark',
      cardClass: 'border-info',
      textClass: 'text-info',
    },
    PERIODIC_INSPECTION_COMPLETED: {
      label: 'Inspección Periódica',
      icon: 'bi-clipboard2-check-fill',
      badgeClass: 'bg-success',
      cardClass: 'border-success',
      textClass: 'text-success',
    },
    WORK_ORDER_DISMISSED_FALSE_POSITIVE: {
      label: 'Desestimado (Falso Positivo)',
      icon: 'bi-shield-check',
      badgeClass: 'bg-success',
      cardClass: 'border-success',
      textClass: 'text-success',
    },
    RECEPTION_REJECTED_BY_AREA: {
      label: 'Recepción Rechazada (Devolución)',
      icon: 'bi-arrow-return-left',
      badgeClass: 'bg-danger',
      cardClass: 'border-danger',
      textClass: 'text-danger',
    },
  }
  return (
    map[type] || {
      label: type.replace(/_/g, ' '),
      icon: 'bi-dot',
      badgeClass: 'bg-secondary',
      cardClass: 'border-secondary',
      textClass: 'text-secondary',
    }
  )
}

function formatTimestamp(ts) {
  if (!ts) return '—'
  return ts.replace('T', ' ').slice(0, 19)
}

function parsedPayload(jsonStr) {
  try {
    return JSON.parse(jsonStr)
  } catch (_) {
    return { detalle: jsonStr }
  }
}

function formatPayloadKey(key) {
  const labels = {
    incident_id: 'ID de Incidencia',
    work_order_id: 'ID Orden de Trabajo',
    severity: 'Severidad',
    symptom: 'Síntoma Reportado',
    previous_state: 'Estado Anterior',
    new_state: 'Nuevo Estado',
    folio_biotrack: 'Folio BioTrack',
    external_lab_folio: 'Folio Laboratorio Externo',
    metrological_result: 'Resultado Metrológico',
    result: 'Resultado',
    diagnosis: 'Diagnóstico Técnico',
    parts_used: 'Refacciones Utilizadas',
    parts_cost: 'Costo de Refacciones ($ USD)',
    biomedical_signature_hash: 'Huella Firma 1 (Biomédico)',
    area_signature_hash: 'Huella Firma 2 (Área)',
    public_qr_token: 'Token QR Público',
    reception_notes: 'Notas de Recepción',
    assigned_biomedical_name: 'Biomédico de Guardia',
    escalated_to_name: 'Escalado a',
    message: 'Mensaje de Seguridad',
    reason: 'Motivo',
  }
  return labels[key] || key.replace(/_/g, ' ')
}

function formatPayloadVal(val) {
  if (val === null || val === undefined || val === '') return '—'
  if (typeof val === 'boolean') return val ? 'Sí' : 'No'
  return String(val)
}

function selectEvent(ev) {
  selectedEvent.value = ev
}

async function searchDossier() {
  if (!query.value.trim()) return
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get(`/audit/assets/${encodeURIComponent(query.value.trim())}`)
    dossier.value = data
    selectedEvent.value = data.audit_events?.length ? data.audit_events[data.audit_events.length - 1] : null
  } catch (err) {
    dossier.value = null
    selectedEvent.value = null
    error.value = err.response?.data?.error || 'No se encontró el expediente.'
  } finally {
    loading.value = false
  }
}

function quickLoad(code) {
  query.value = code
  searchDossier()
}

async function reverify() {
  if (!dossier.value) return
  const { data } = await api.get(`/audit/assets/${dossier.value.asset.id}/verify`)
  dossier.value.integrity = data.integrity
}

function printFullReport() {
  window.print()
}

onMounted(searchDossier)
</script>
