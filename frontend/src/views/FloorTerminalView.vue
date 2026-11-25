<template>
  <div class="container-lg py-4">
    <!-- Persistent Red Fail-Safe Banner if any asset in current area is BLOQUEADO -->
    <div v-if="blockedAssets.length" class="alert failsafe-banner shadow mb-4 p-3">
      <div class="d-flex align-items-center gap-3">
        <i class="bi bi-exclamation-octagon-fill display-5"></i>
        <div>
          <h4 class="fw-bold mb-1">EQUIPO BLOQUEADO POR SEGURIDAD — RETIRAR DE ATENCIÓN A PACIENTES</h4>
          <div v-for="b in blockedAssets" :key="b.id" class="fw-semibold">
            • {{ b.inventory_code }} ({{ b.device_type }} {{ b.brand }} {{ b.model }}) — Fuera de servicio hasta Doble Validación (Biomédica + Responsable de Área).
          </div>
        </div>
      </div>
    </div>

    <!-- Header + Terminal Area Binding (AD-04) -->
    <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
      <div>
        <h3 class="fw-bold mb-0">
          <i class="bi bi-hospital-fill text-primary me-2"></i>Terminal Clínica de Piso
        </h3>
        <div class="text-muted small">
          Reporte rápido optimizado para tabletas (&lt; 30 s · QA-02)
        </div>
      </div>
      <div class="d-flex align-items-center gap-2">
        <span class="small fw-semibold text-muted">Área de esta terminal:</span>
        <select
          class="form-select w-auto fw-semibold"
          :value="selectedAreaId"
          @change="changeArea($event.target.value)"
        >
          <option v-for="area in auth.areas" :key="area.id" :value="area.id">
            {{ area.name }} ({{ area.area_code }})
          </option>
        </select>
      </div>
    </div>

    <!-- Visual Stepper Header: 1. Seleccionar equipo > 2. Seleccionar síntoma > 3. Confirmar y enviar -->
    <div class="card border-0 shadow-sm mb-4">
      <div class="card-body py-3 px-3 px-md-4">
        <div class="d-flex flex-column flex-md-row align-items-stretch align-items-md-center justify-content-between gap-2">
          <div
            :class="[
              'd-flex align-items-center gap-2 px-3 py-2 rounded-3 flex-fill',
              selectedAsset ? 'bg-success-subtle text-success-emphasis border border-success' : 'bg-primary text-white shadow-sm'
            ]"
          >
            <i :class="['bi fs-5', selectedAsset ? 'bi-check-circle-fill' : 'bi-1-circle-fill']"></i>
            <div>
              <div class="fw-bold small">1. Seleccionar equipo</div>
              <div class="opacity-75" style="font-size: 0.75rem">
                {{ selectedAsset ? selectedAsset.inventory_code : 'Toque una tarjeta' }}
              </div>
            </div>
          </div>

          <i class="bi bi-chevron-right text-muted d-none d-md-inline fs-5"></i>

          <div
            :class="[
              'd-flex align-items-center gap-2 px-3 py-2 rounded-3 flex-fill',
              selectedSymptom
                ? 'bg-success-subtle text-success-emphasis border border-success'
                : selectedAsset
                ? 'bg-primary text-white shadow-sm'
                : 'bg-light text-muted border'
            ]"
          >
            <i :class="['bi fs-5', selectedSymptom ? 'bi-check-circle-fill' : 'bi-2-circle-fill']"></i>
            <div>
              <div class="fw-bold small">2. Seleccionar síntoma</div>
              <div class="opacity-75 text-truncate" style="font-size: 0.75rem; max-width: 210px">
                {{ selectedSymptom ? selectedSymptom.description : 'Elija del catálogo' }}
              </div>
            </div>
          </div>

          <i class="bi bi-chevron-right text-muted d-none d-md-inline fs-5"></i>

          <div
            :class="[
              'd-flex align-items-center gap-2 px-3 py-2 rounded-3 flex-fill',
              selectedAsset && selectedSymptom ? 'bg-primary text-white shadow-sm' : 'bg-light text-muted border'
            ]"
          >
            <i class="bi bi-3-circle-fill fs-5"></i>
            <div>
              <div class="fw-bold small">3. Confirmar y enviar</div>
              <div class="opacity-75" style="font-size: 0.75rem">
                {{ selectedAsset && selectedSymptom ? `Severidad: ${severity}` : 'Pendiente' }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Success confirmation banner -->
    <div v-if="lastResult" :class="['alert shadow-sm mb-4', lastResult.failsafe_triggered ? 'alert-danger' : 'alert-success']">
      <div class="d-flex justify-content-between align-items-start">
        <div>
          <h5 class="fw-bold mb-1">
            <i :class="['bi me-2', lastResult.failsafe_triggered ? 'bi-shield-exclamation' : 'bi-check-circle-fill']"></i>
            {{ lastResult.failsafe_triggered ? 'BLOQUEO FAIL-SAFE EJECUTADO ATÓMICAMENTE' : 'Reporte registrado correctamente' }}
          </h5>
          <p class="mb-1">
            Equipo <strong>{{ lastResult.asset.inventory_code }}</strong> ahora en estado
            <strong>{{ lastResult.asset.current_state }}</strong>. Orden de trabajo #{{ lastResult.work_order.id }} generada.
          </p>
          <p v-if="lastResult.dispatch_alert" class="mb-0 small">
            <i class="bi bi-bell-fill me-1"></i>
            Aviso prioritario despachado al biomédico de guardia:
            <strong>{{ lastResult.dispatch_alert.assigned_biomedical_name }}</strong>
            ({{ lastResult.dispatch_alert.assigned_phone }}).
          </p>
        </div>
        <button class="btn-close" @click="lastResult = null"></button>
      </div>
    </div>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <!-- 3-STEP WIZARD (Tablet-responsive grid) -->
    <div class="row g-4">
      <!-- STEP 1: Select Asset -->
      <div class="col-12 col-lg-7">
        <div class="card shadow-sm border-0 h-100">
          <div class="card-header bg-white fw-bold py-3">
            <span class="badge bg-primary rounded-pill me-2">Paso 1</span>
            Seleccione el equipo médico en {{ currentAreaName }}
          </div>
          <div class="card-body">
            <div class="row g-3">
              <div v-for="asset in areaAssets" :key="asset.id" class="col-12 col-sm-6">
                <div
                  @click="selectAsset(asset)"
                  :class="[
                    'card asset-card-touch h-100',
                    selectedAsset?.id === asset.id ? 'border-primary bg-primary-subtle' : 'border-light-subtle',
                    asset.current_state !== 'OPERATIVO' ? 'opacity-75' : ''
                  ]"
                >
                  <div class="card-body p-3">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                      <span class="fw-bold fs-5 text-dark">{{ asset.inventory_code }}</span>
                      <StatusBadge :state="asset.current_state" />
                    </div>
                    <div class="fw-semibold text-primary">{{ asset.device_type }}</div>
                    <div class="small text-muted">{{ asset.brand }} {{ asset.model }}</div>
                    <div class="small text-muted mt-1">
                      <i class="bi bi-upc me-1"></i>{{ asset.serial_number }}
                    </div>
                    <span
                      v-if="asset.risk_class === 'SOPORTE_VIDA'"
                      class="badge bg-danger-subtle text-danger mt-2"
                    >
                      <i class="bi bi-heart-pulse me-1"></i>Soporte de Vida
                    </span>
                  </div>
                </div>
              </div>
              <div v-if="!areaAssets.length" class="col-12 text-center text-muted py-4">
                No hay equipos registrados en esta área.
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- STEP 2 & 3: Symptom Catalog, Optional Tablet Textarea & Severity Submit -->
      <div class="col-12 col-lg-5">
        <div class="card shadow-sm border-0 mb-3">
          <div class="card-header bg-white fw-bold py-3">
            <span class="badge bg-primary rounded-pill me-2">Paso 2</span>
            Seleccione el síntoma tipificado
          </div>
          <div class="card-body">
            <div v-if="!selectedAsset" class="text-muted text-center py-4">
              <i class="bi bi-arrow-left-circle fs-3 d-block mb-2"></i>
              Toque un equipo en estado <strong>Operativo</strong> del Paso 1.
            </div>
            <div v-else>
              <div class="mb-2 small text-muted">
                Catálogo para <strong>{{ selectedAsset.device_type }}</strong>:
              </div>
              <div class="d-grid gap-2">
                <button
                  v-for="sym in filteredSymptoms"
                  :key="sym.id"
                  type="button"
                  @click="selectSymptom(sym)"
                  :class="[
                    'btn btn-lg text-start py-3 px-3 d-flex justify-content-between align-items-center fs-6',
                    selectedSymptom?.id === sym.id ? 'btn-primary' : 'btn-outline-dark'
                  ]"
                >
                  <span>{{ sym.description }}</span>
                  <span
                    :class="[
                      'badge ms-2',
                      sym.default_severity === 'CRITICA' ? 'bg-danger' : sym.default_severity === 'MEDIA' ? 'bg-warning text-dark' : 'bg-secondary'
                    ]"
                  >
                    {{ sym.default_severity }}
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="card shadow-sm border-0">
          <div class="card-header bg-white fw-bold py-3">
            <span class="badge bg-primary rounded-pill me-2">Paso 3</span>
            Confirme severidad, notas y envíe
          </div>
          <div class="card-body">
            <div class="btn-group btn-group-lg w-100 mb-3" role="group">
              <button
                type="button"
                @click="severity = 'BAJA'"
                :class="['btn py-2', severity === 'BAJA' ? 'btn-secondary' : 'btn-outline-secondary']"
              >
                Baja
              </button>
              <button
                type="button"
                @click="severity = 'MEDIA'"
                :class="['btn py-2', severity === 'MEDIA' ? 'btn-warning' : 'btn-outline-warning']"
              >
                Media
              </button>
              <button
                type="button"
                @click="severity = 'CRITICA'"
                :class="['btn py-2 fw-bold', severity === 'CRITICA' ? 'btn-danger' : 'btn-outline-danger']"
              >
                <i class="bi bi-exclamation-octagon-fill me-1"></i>CRÍTICA
              </button>
            </div>

            <!-- Tablet-friendly optional clinical notes textarea -->
            <div class="mb-3">
              <label class="form-label small fw-semibold text-muted">
                <i class="bi bi-chat-left-text me-1"></i>Observaciones para Taller Biomédico (opcional)
              </label>
              <textarea
                v-model="clinicalNotes"
                class="form-control"
                rows="3"
                placeholder="Ej. Ocurrió al iniciar infusión en cama 4; pantalla mostró código E-14..."
              ></textarea>
            </div>

            <div class="form-check form-switch mb-3 small">
              <input v-model="isDeferred" class="form-check-input" type="checkbox" id="deferredSwitch" />
              <label class="form-check-label text-muted" for="deferredSwitch">
                Registro diferido por contingencia sin red (SDS Sec. 7)
              </label>
            </div>
            <div v-if="isDeferred" class="mb-3">
              <label class="form-label small">Hora declarada del evento en formato físico:</label>
              <input v-model="declaredAt" type="datetime-local" class="form-control" />
            </div>

            <button
              type="button"
              :class="['btn btn-lg w-100 py-3 fw-bold', severity === 'CRITICA' ? 'btn-danger' : 'btn-primary']"
              :disabled="!selectedAsset || !selectedSymptom || submitting"
              @click="submitReport"
            >
              <span v-if="submitting" class="spinner-border spinner-border-sm me-2"></span>
              <i v-else class="bi bi-send-exclamation-fill me-2"></i>
              {{ severity === 'CRITICA' ? 'BLOQUEAR EQUIPO Y AVISAR A GUARDIA' : 'Enviar Reporte a Biomédica' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useAlertsStore } from '../stores/alerts'
import StatusBadge from '../components/StatusBadge.vue'

const auth = useAuthStore()
const alerts = useAlertsStore()

const assets = ref([])
const symptoms = ref([])
const selectedAsset = ref(null)
const selectedSymptom = ref(null)
const severity = ref('MEDIA')
const clinicalNotes = ref('')
const isDeferred = ref(false)
const declaredAt = ref('')
const submitting = ref(false)
const error = ref('')
const lastResult = ref(null)

const selectedAreaId = computed(() => auth.terminalAreaId || auth.areas[0]?.id || 1)
const currentAreaName = computed(() => auth.areas.find((a) => a.id === selectedAreaId.value)?.name || 'Área Clínica')

const areaAssets = computed(() => assets.value.filter((a) => a.area_id === selectedAreaId.value))
const blockedAssets = computed(() => areaAssets.value.filter((a) => a.current_state === 'BLOQUEADO'))

const filteredSymptoms = computed(() => {
  if (!selectedAsset.value) return []
  const exact = symptoms.value.filter((s) => s.device_type === selectedAsset.value.device_type)
  return exact.length ? exact : symptoms.value
})

async function loadData() {
  const [aRes, sRes] = await Promise.all([api.get('/assets'), api.get('/assets/symptoms')])
  assets.value = aRes.data.assets || []
  symptoms.value = sRes.data.symptoms || []
}

function changeArea(areaId) {
  auth.setTerminalArea(Number(areaId))
  selectedAsset.value = null
  selectedSymptom.value = null
}

function selectAsset(asset) {
  if (asset.current_state !== 'OPERATIVO') {
    error.value = `El equipo ${asset.inventory_code} no está Operativo (estado actual: ${asset.current_state}).`
    return
  }
  error.value = ''
  selectedAsset.value = asset
  selectedSymptom.value = null
}

function selectSymptom(sym) {
  selectedSymptom.value = sym
  severity.value = sym.default_severity
}

async function submitReport() {
  if (!selectedAsset.value || !selectedSymptom.value) return
  submitting.value = true
  error.value = ''
  try {
    const payload = {
      asset_id: selectedAsset.value.id,
      symptom_id: selectedSymptom.value.id,
      symptom_text: selectedSymptom.value.description,
      severity: severity.value,
      notes: clinicalNotes.value.trim() || null,
      is_deferred: isDeferred.value,
      declared_occurred_at: isDeferred.value && declaredAt.value ? declaredAt.value : null,
    }
    const { data } = await api.post('/incidents', payload)
    lastResult.value = data
    selectedAsset.value = null
    selectedSymptom.value = null
    clinicalNotes.value = ''
    await loadData()
    await alerts.fetchAlerts()
  } catch (err) {
    error.value = err.response?.data?.error || 'No se pudo registrar el reporte.'
  } finally {
    submitting.value = false
  }
}

onMounted(loadData)
</script>
