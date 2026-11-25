<template>
  <div class="container-fluid py-4 px-4">
    <!-- Scenario 5: Preventive Maintenance Due Alert -->
    <div v-if="dueAssets.length" class="card border-warning shadow-sm mb-4">
      <div class="card-header bg-warning-subtle fw-bold d-flex justify-content-between align-items-center">
        <span>
          <i class="bi bi-calendar-event-fill text-warning me-2"></i>
          Mantenimientos Preventivos por Vencer (≤ 15 días) o Vencidos: {{ dueAssets.length }}
        </span>
        <span class="small text-muted">Escenario 5 ConOps v0.2</span>
      </div>
      <div class="table-responsive">
        <table class="table table-sm align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th>Activo</th>
              <th>Equipo</th>
              <th>Área</th>
              <th>Próximo Preventivo</th>
              <th>Estado</th>
              <th v-if="isBiomed">Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in dueAssets" :key="a.id">
              <td class="fw-bold">{{ a.inventory_code }}</td>
              <td>{{ a.device_type }} <span class="text-muted small">({{ a.brand }} {{ a.model }})</span></td>
              <td>{{ a.area_name }}</td>
              <td>
                <span :class="['badge', a.days_remaining < 0 ? 'bg-danger' : 'bg-warning text-dark']">
                  {{ a.next_preventive_date }} ({{ a.days_remaining < 0 ? `Vencido ${Math.abs(a.days_remaining)}d` : `En ${a.days_remaining} días` }})
                </span>
              </td>
              <td><StatusBadge :state="a.current_state" /></td>
              <td v-if="isBiomed">
                <button
                  v-if="a.current_state === 'OPERATIVO'"
                  class="btn btn-outline-primary btn-sm me-1"
                  @click="startPreventive(a)"
                >
                  <i class="bi bi-tools me-1"></i>Iniciar Preventivo
                </button>
                <button
                  v-if="a.current_state === 'OPERATIVO'"
                  class="btn btn-outline-success btn-sm"
                  @click="runInspection(a)"
                >
                  <i class="bi bi-clipboard2-check me-1"></i>Inspección Rápida
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Full Asset Inventory -->
    <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
      <h3 class="fw-bold mb-0"><i class="bi bi-cpu-fill text-primary me-2"></i>Inventario de Equipamiento Médico</h3>
      <input
        v-model="search"
        type="search"
        class="form-control form-control-sm"
        style="max-width: 280px"
        placeholder="Buscar por código, serie o modelo..."
      />
    </div>

    <div v-if="feedback" class="alert alert-success">{{ feedback }}</div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <div class="card border-0 shadow-sm">
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th>Código</th>
              <th>N° Serie</th>
              <th>Dispositivo</th>
              <th>Área</th>
              <th>Riesgo</th>
              <th>Estado</th>
              <th>Próx. Preventivo</th>
              <th>Etiqueta QR</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="asset in filteredAssets" :key="asset.id">
              <td class="fw-bold">{{ asset.inventory_code }}</td>
              <td><code>{{ asset.serial_number }}</code></td>
              <td>
                <div class="fw-semibold">{{ asset.device_type }}</div>
                <div class="small text-muted">{{ asset.brand }} {{ asset.model }}</div>
              </td>
              <td>{{ asset.area_name }}</td>
              <td>
                <span :class="['badge', asset.risk_class === 'SOPORTE_VIDA' ? 'bg-danger-subtle text-danger' : 'bg-secondary-subtle text-secondary']">
                  {{ asset.risk_class === 'SOPORTE_VIDA' ? 'Soporte Vida' : 'No Crítico' }}
                </span>
              </td>
              <td><StatusBadge :state="asset.current_state" /></td>
              <td class="small">{{ asset.next_preventive_date || '—' }}</td>
              <td>
                <button
                  v-if="asset.latest_certification"
                  class="btn btn-outline-dark btn-sm"
                  @click="openSticker(asset)"
                >
                  <i class="bi bi-qr-code me-1"></i>{{ asset.latest_certification.folio_biotrack }}
                </button>
                <span v-else class="text-muted small">Sin folio</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <StickerPrintModal
      :visible="Boolean(stickerCert)"
      :certification="stickerCert"
      :asset="stickerAsset"
      @close="stickerCert = null"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import StatusBadge from '../components/StatusBadge.vue'
import StickerPrintModal from '../components/StickerPrintModal.vue'

const auth = useAuthStore()
const assets = ref([])
const dueAssets = ref([])
const search = ref('')
const feedback = ref('')
const error = ref('')

const stickerCert = ref(null)
const stickerAsset = ref(null)

const isBiomed = computed(() => ['BIOMEDICO', 'JEFE_TALLER'].includes(auth.role))

const filteredAssets = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return assets.value
  return assets.value.filter(
    (a) =>
      a.inventory_code.toLowerCase().includes(q) ||
      a.serial_number.toLowerCase().includes(q) ||
      a.device_type.toLowerCase().includes(q) ||
      a.brand.toLowerCase().includes(q) ||
      a.model.toLowerCase().includes(q)
  )
})

async function loadAll() {
  const [aRes, dRes] = await Promise.all([api.get('/assets'), api.get('/assets/preventive-due?days=15')])
  assets.value = aRes.data.assets || []
  dueAssets.value = dRes.data.assets || []
}

async function startPreventive(asset) {
  error.value = ''
  try {
    await api.post(`/assets/${asset.id}/preventive-start`, { notes: 'Retiro coordinado con jefatura de enfermería.' })
    feedback.value = `Mantenimiento preventivo iniciado para ${asset.inventory_code}. Continúe en Taller Biomédico.`
    await loadAll()
  } catch (err) {
    error.value = err.response?.data?.error || 'Error al iniciar preventivo.'
  }
}

async function runInspection(asset) {
  error.value = ''
  try {
    const { data } = await api.post(`/assets/${asset.id}/inspect`, {
      result_notes: 'Inspección periódica de funcionamiento y seguridad eléctrica aprobada.',
    })
    feedback.value = `Inspección completada. Nuevo folio: ${data.certification.folio_biotrack}.`
    stickerCert.value = data.certification
    stickerAsset.value = data.asset
    await loadAll()
  } catch (err) {
    error.value = err.response?.data?.error || 'Error al registrar inspección.'
  }
}

function openSticker(asset) {
  stickerAsset.value = asset
  stickerCert.value = asset.latest_certification
}

onMounted(loadAll)
</script>
