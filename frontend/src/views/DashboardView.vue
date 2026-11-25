<template>
  <div class="container-fluid py-4 px-4">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <div>
        <h3 class="fw-bold mb-0">
          <i class="bi bi-graph-up-arrow text-primary me-2"></i>Cuadro de Mando Directivo (5 Indicadores ConOps v0.2)
        </h3>
        <div class="text-muted small">
          Disponibilidad, MTTR, recurrencia de fallas, cumplimiento preventivo y análisis costo refacciones vs reposición (Escenario 4)
        </div>
      </div>
      <button class="btn btn-outline-primary btn-sm" @click="loadKpis">
        <i class="bi bi-arrow-clockwise me-1"></i>Actualizar
      </button>
    </div>

    <div v-if="kpis">
      <!-- Top KPI Cards -->
      <div class="row g-3 mb-4">
        <div class="col-md-3">
          <div class="card border-0 shadow-sm h-100 border-start border-4 border-success">
            <div class="card-body">
              <div class="text-muted small text-uppercase fw-semibold">1. Disponibilidad Global</div>
              <div class="display-6 fw-bold text-success">{{ kpis.summary.overall_availability_pct }}%</div>
              <div class="small text-muted">
                {{ kpis.summary.operative_assets }} / {{ kpis.summary.total_active_assets }} operativos
                <span v-if="kpis.summary.blocked_assets" class="text-danger fw-bold">
                  ({{ kpis.summary.blocked_assets }} bloqueados)
                </span>
              </div>
            </div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="card border-0 shadow-sm h-100 border-start border-4 border-primary">
            <div class="card-body">
              <div class="text-muted small text-uppercase fw-semibold">2. Tiempo Medio Reingreso (MTTR)</div>
              <div class="display-6 fw-bold text-primary">{{ kpis.summary.mttr_hours }} h</div>
              <div class="small text-muted">Promedio reporte → reingreso operativo</div>
            </div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="card border-0 shadow-sm h-100 border-start border-4 border-info">
            <div class="card-body">
              <div class="text-muted small text-uppercase fw-semibold">4. Cumplimiento Preventivo</div>
              <div class="display-6 fw-bold text-info">{{ kpis.summary.preventive_compliance_pct }}%</div>
              <div class="small text-muted">
                Al día: {{ kpis.preventive_compliance.on_time }} · Por vencer: {{ kpis.preventive_compliance.due_soon_15d }} · Vencidos: {{ kpis.preventive_compliance.overdue }}
              </div>
            </div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="card border-0 shadow-sm h-100 border-start border-4 border-danger">
            <div class="card-body">
              <div class="text-muted small text-uppercase fw-semibold">5. Candidatos a Reemplazo (Capex)</div>
              <div class="display-6 fw-bold text-danger">{{ kpis.summary.replacement_candidates_count }}</div>
              <div class="small text-muted">Activos con desgaste o costo crítico</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Charts Row -->
      <div class="row g-4 mb-4">
        <div class="col-lg-5">
          <div class="card border-0 shadow-sm h-100">
            <div class="card-header bg-white fw-bold">Disponibilidad por Área Clínica (%)</div>
            <div class="card-body">
              <canvas ref="areaChartEl" height="220"></canvas>
            </div>
          </div>
        </div>
        <div class="col-lg-4">
          <div class="card border-0 shadow-sm h-100">
            <div class="card-header bg-white fw-bold">3. Equipos con Mayor Recurrencia de Fallas</div>
            <div class="card-body">
              <canvas ref="failuresChartEl" height="220"></canvas>
            </div>
          </div>
        </div>
        <div class="col-lg-3">
          <div class="card border-0 shadow-sm h-100">
            <div class="card-header bg-white fw-bold">4. Programa Preventivo</div>
            <div class="card-body d-flex align-items-center justify-content-center">
              <canvas ref="preventiveChartEl" height="220"></canvas>
            </div>
          </div>
        </div>
      </div>

      <!-- KPI 5 Table: Parts Cost vs Replacement Cost -->
      <div class="card border-0 shadow-sm">
        <div class="card-header bg-white fw-bold">
          5. Costo Acumulado de Refacciones vs. Valor de Reposición (Decisión de Inversión Capex)
        </div>
        <div class="table-responsive">
          <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
              <tr>
                <th>Activo</th>
                <th>Dispositivo</th>
                <th>Área</th>
                <th class="text-center">Fallas (12m)</th>
                <th class="text-end">Refacciones Acum.</th>
                <th class="text-end">Valor Reposición</th>
                <th style="width: 180px">Relación Costo</th>
                <th>Recomendación</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in kpis.cost_vs_replacement" :key="m.asset_id">
                <td class="fw-bold">{{ m.inventory_code }}</td>
                <td>
                  <div>{{ m.device_type }}</div>
                  <div class="small text-muted">{{ m.brand }} {{ m.model }}</div>
                </td>
                <td>{{ m.area_name }}</td>
                <td class="text-center fw-semibold">{{ m.failure_count }}</td>
                <td class="text-end">${{ m.cumulative_parts_cost.toLocaleString() }}</td>
                <td class="text-end">${{ m.replacement_cost.toLocaleString() }}</td>
                <td>
                  <div class="progress" style="height: 18px">
                    <div
                      :class="[
                        'progress-bar fw-semibold',
                        m.cost_ratio_pct >= 60 ? 'bg-danger' : m.cost_ratio_pct >= 35 ? 'bg-warning text-dark' : 'bg-success',
                      ]"
                      :style="{ width: Math.min(m.cost_ratio_pct, 100) + '%' }"
                    >
                      {{ m.cost_ratio_pct }}%
                    </div>
                  </div>
                </td>
                <td>
                  <span
                    :class="[
                      'badge',
                      m.recommendation === 'REEMPLAZO_URGENTE'
                        ? 'bg-danger'
                        : m.recommendation === 'EVALUAR_SUSTITUCION'
                        ? 'bg-warning text-dark'
                        : 'bg-success',
                    ]"
                  >
                    {{ m.recommendation.replace(/_/g, ' ') }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { Chart, registerables } from 'chart.js'
import api from '../services/api'

Chart.register(...registerables)

const kpis = ref(null)
const areaChartEl = ref(null)
const failuresChartEl = ref(null)
const preventiveChartEl = ref(null)

let charts = []

function destroyCharts() {
  charts.forEach((c) => c.destroy())
  charts = []
}

async function loadKpis() {
  const { data } = await api.get('/analytics/kpis')
  kpis.value = data
  await nextTick()
  renderCharts()
}

function renderCharts() {
  destroyCharts()
  if (!kpis.value) return

  if (areaChartEl.value) {
    charts.push(
      new Chart(areaChartEl.value, {
        type: 'bar',
        data: {
          labels: kpis.value.availability_by_area.map((a) => a.area_name),
          datasets: [
            {
              label: '% Operativos',
              data: kpis.value.availability_by_area.map((a) => a.availability_pct),
              backgroundColor: '#198754',
              borderRadius: 6,
            },
          ],
        },
        options: { scales: { y: { beginAtZero: true, max: 100 } }, plugins: { legend: { display: false } } },
      })
    )
  }

  if (failuresChartEl.value) {
    const top = kpis.value.top_recurring_failures.filter((x) => x.failure_count > 0)
    charts.push(
      new Chart(failuresChartEl.value, {
        type: 'bar',
        data: {
          labels: top.map((x) => x.inventory_code),
          datasets: [
            {
              label: 'Fallas Correctivas',
              data: top.map((x) => x.failure_count),
              backgroundColor: '#dc3545',
              borderRadius: 6,
            },
          ],
        },
        options: { indexAxis: 'y', plugins: { legend: { display: false } } },
      })
    )
  }

  if (preventiveChartEl.value) {
    const p = kpis.value.preventive_compliance
    charts.push(
      new Chart(preventiveChartEl.value, {
        type: 'doughnut',
        data: {
          labels: ['Al día', 'Por vencer (≤15d)', 'Vencidos'],
          datasets: [
            {
              data: [p.on_time, p.due_soon_15d, p.overdue],
              backgroundColor: ['#198754', '#ffc107', '#dc3545'],
            },
          ],
        },
      })
    )
  }
}

onMounted(loadKpis)
onUnmounted(destroyCharts)
</script>
