<template>
  <div class="container py-4">
    <h3 class="fw-bold mb-1">
      <i class="bi bi-telephone-inbound-fill text-primary me-2"></i>Rol de Guardias Biomédicas (On-Call Roster)
    </h3>
    <p class="text-muted small mb-4">
      Catálogo de turnos activos para despacho prioritario y escalamiento automático al Jefe de Taller (AD-05, QA-07).
    </p>

    <div class="row g-4">
      <!-- Active Roster Table -->
      <div class="col-lg-8">
        <div class="card border-0 shadow-sm mb-4">
          <div class="card-header bg-white fw-bold">Guardias Registradas</div>
          <div class="table-responsive">
            <table class="table align-middle mb-0">
              <thead class="table-light">
                <tr>
                  <th>Especialista</th>
                  <th>Teléfono</th>
                  <th>Vigencia</th>
                  <th>Estado</th>
                  <th>Acción</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in rosters" :key="r.id">
                  <td>
                    <div class="fw-semibold">{{ r.biomedical_name }}</div>
                    <div class="small text-muted">{{ r.biomedical_role }}</div>
                  </td>
                  <td><i class="bi bi-phone me-1"></i>{{ r.contact_phone }}</td>
                  <td class="small">
                    {{ r.start_time?.slice(0, 16).replace('T', ' ') }} →<br />
                    {{ r.end_time?.slice(0, 16).replace('T', ' ') }}
                  </td>
                  <td>
                    <span :class="['badge', r.is_active ? 'bg-success' : 'bg-secondary']">
                      {{ r.is_active ? 'Activa' : 'Inactiva' }}
                    </span>
                  </td>
                  <td>
                    <button class="btn btn-sm btn-outline-secondary" @click="toggleActive(r)">
                      {{ r.is_active ? 'Desactivar' : 'Activar' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Dispatch History -->
        <div class="card border-0 shadow-sm">
          <div class="card-header bg-white fw-bold d-flex justify-content-between align-items-center">
            <span>Bitácora de Despacho Activo y Escalamientos</span>
            <button class="btn btn-sm btn-outline-danger" @click="alerts.checkEscalations()">
              Verificar Escalamientos
            </button>
          </div>
          <div class="table-responsive">
            <table class="table table-sm align-middle mb-0">
              <thead class="table-light">
                <tr>
                  <th>Estado</th>
                  <th>Activo / Área</th>
                  <th>Guardia</th>
                  <th>Escalado a</th>
                  <th>Despachado</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="a in alerts.alerts" :key="a.id">
                  <td>
                    <span
                      :class="[
                        'badge',
                        a.status === 'ESCALADO'
                          ? 'bg-dark'
                          : a.status === 'PENDIENTE'
                          ? 'bg-danger'
                          : a.status === 'ACUSADO'
                          ? 'bg-warning text-dark'
                          : 'bg-success',
                      ]"
                    >
                      {{ a.status }}
                    </span>
                  </td>
                  <td class="small">
                    <strong>{{ a.asset_inventory_code }}</strong> ({{ a.area_name }})
                  </td>
                  <td class="small">{{ a.assigned_biomedical_name || '—' }}</td>
                  <td class="small text-danger fw-semibold">{{ a.escalated_to_name || '—' }}</td>
                  <td class="small text-muted">{{ a.dispatched_at?.slice(0, 19).replace('T', ' ') }}</td>
                </tr>
                <tr v-if="!alerts.alerts.length">
                  <td colspan="5" class="text-center text-muted py-3 small">Sin alertas críticas despachadas aún.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Add Roster Shift -->
      <div class="col-lg-4">
        <div class="card border-0 shadow-sm">
          <div class="card-header bg-white fw-bold">Programar Guardia</div>
          <div class="card-body">
            <div v-if="feedback" class="alert alert-success py-2 small">{{ feedback }}</div>
            <form @submit.prevent="createShift">
              <div class="mb-2">
                <label class="form-label small fw-semibold">Ingeniero Biomédico</label>
                <select v-model="form.biomedical_user_id" class="form-select form-select-sm" required>
                  <option v-for="u in staff" :key="u.id" :value="u.id">
                    {{ u.full_name }} ({{ u.role }})
                  </option>
                </select>
              </div>
              <div class="mb-2">
                <label class="form-label small fw-semibold">Teléfono de contacto directo</label>
                <input v-model="form.contact_phone" class="form-control form-control-sm" placeholder="33-3614-2001" required />
              </div>
              <div class="mb-2">
                <label class="form-label small fw-semibold">Inicio de guardia</label>
                <input v-model="form.start_time" type="datetime-local" class="form-control form-control-sm" required />
              </div>
              <div class="mb-3">
                <label class="form-label small fw-semibold">Fin de guardia</label>
                <input v-model="form.end_time" type="datetime-local" class="form-control form-control-sm" required />
              </div>
              <button type="submit" class="btn btn-primary btn-sm w-100">Guardar Guardia</button>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../services/api'
import { useAlertsStore } from '../stores/alerts'

const alerts = useAlertsStore()
const rosters = ref([])
const staff = ref([])
const feedback = ref('')

const now = new Date()
const tomorrow = new Date(now.getTime() + 24 * 3600 * 1000)

const form = reactive({
  biomedical_user_id: '',
  contact_phone: '33-3614-2001',
  start_time: now.toISOString().slice(0, 16),
  end_time: tomorrow.toISOString().slice(0, 16),
})

async function loadAll() {
  const [rRes, sRes] = await Promise.all([api.get('/oncall/roster'), api.get('/auth/biomedical-staff')])
  rosters.value = rRes.data.rosters || []
  staff.value = sRes.data.staff || []
  if (staff.value.length && !form.biomedical_user_id) {
    form.biomedical_user_id = staff.value[0].id
  }
  await alerts.fetchAlerts()
}

async function createShift() {
  await api.post('/oncall/roster', { ...form, coverage_areas: [], is_active: true })
  feedback.value = 'Guardia registrada correctamente.'
  await loadAll()
}

async function toggleActive(roster) {
  await api.patch(`/oncall/roster/${roster.id}`, { is_active: !roster.is_active })
  await loadAll()
}

onMounted(loadAll)
</script>
