<template>
  <div v-if="visible" class="modal d-block" tabindex="-1" style="background: rgba(0, 0, 0, 0.55)">
    <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
      <div class="modal-content shadow-lg border-0">
        <div class="modal-header bg-primary text-white">
          <h5 class="modal-title fw-bold">
            <i class="bi bi-compass-fill me-2"></i>Guía Paso a Paso — Hospital BioTrack
          </h5>
          <button type="button" class="btn-close btn-close-white" @click="$emit('close')"></button>
        </div>

        <div class="modal-body p-4">
          <p class="text-muted small mb-3">
            Seleccione un perfil para ver las instrucciones rápidas paso a paso. Por defecto se muestra la guía de su rol actual.
          </p>

          <!-- Role Tabs -->
          <ul class="nav nav-pills flex-wrap gap-1 mb-4">
            <li v-for="g in guides" :key="g.role" class="nav-item">
              <button
                type="button"
                @click="activeRole = g.role"
                :class="['nav-link btn-sm py-2 px-3', activeRole === g.role ? 'active fw-semibold' : 'bg-light text-dark']"
              >
                <i :class="['bi me-1', g.icon]"></i>{{ g.title }}
                <span v-if="g.role === currentRole" class="badge bg-warning text-dark ms-1">Tú</span>
              </button>
            </li>
          </ul>

          <!-- Active Role Guide Content -->
          <div v-if="currentGuide" class="card border-0 bg-light">
            <div class="card-body p-4">
              <div class="d-flex align-items-center gap-2 mb-3">
                <i :class="['bi fs-3 text-primary', currentGuide.icon]"></i>
                <div>
                  <h5 class="fw-bold mb-0">{{ currentGuide.title }}</h5>
                  <div class="small text-muted">{{ currentGuide.subtitle }}</div>
                </div>
              </div>

              <div class="d-flex flex-column gap-3">
                <div
                  v-for="(step, idx) in currentGuide.steps"
                  :key="idx"
                  class="d-flex align-items-start gap-3 bg-white p-3 rounded border shadow-sm"
                >
                  <span class="badge bg-primary rounded-circle d-flex align-items-center justify-content-center fs-6" style="width: 34px; height: 34px; flex-shrink: 0">
                    {{ idx + 1 }}
                  </span>
                  <div>
                    <div class="fw-bold text-dark">{{ step.heading }}</div>
                    <div class="small text-muted">{{ step.detail }}</div>
                  </div>
                </div>
              </div>

              <div v-if="currentGuide.tip" class="alert alert-info mt-3 mb-0 small py-2">
                <i class="bi bi-lightbulb-fill me-1"></i><strong>Consejo rápido:</strong> {{ currentGuide.tip }}
              </div>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn btn-primary btn-lg px-4" @click="$emit('close')">
            Entendido
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  visible: Boolean,
  currentRole: { type: String, default: 'CLINICO' },
})
defineEmits(['close'])

const activeRole = ref(props.currentRole || 'CLINICO')

watch(
  () => [props.visible, props.currentRole],
  ([vis, role]) => {
    if (vis && role) activeRole.value = role
  }
)

const guides = [
  {
    role: 'CLINICO',
    title: 'Personal Clínico',
    subtitle: 'Reporte rápido en Terminal de Piso (< 30 segundos)',
    icon: 'bi-hospital-fill',
    steps: [
      { heading: '1. Seleccionar equipo', detail: 'Verifique el área clínica en la parte superior y toque la tarjeta del equipo que presenta anomalía.' },
      { heading: '2. Seleccionar síntoma', detail: 'Elija el síntoma de la lista predefinida. Si lo desea, agregue notas clínicas breves en el cuadro de texto.' },
      { heading: '3. Confirmar severidad y enviar', detail: 'Confirme si es Baja, Media o Crítica y presione Enviar. Si es Crítica, el equipo se bloquea al instante (Fail-Safe) y avisa al biomédico de guardia.' },
    ],
    tip: 'Si aparece la barra roja de BLOQUEADO, retire el equipo del paciente y use un respaldo hasta que Biomédica y el Responsable de Área completen la Doble Validación.',
  },
  {
    role: 'BIOMEDICO',
    title: 'Ing. Biomédico',
    subtitle: 'Taller Biomédico, calibración, Firma 1 y preventivos',
    icon: 'bi-wrench-adjustable-circle-fill',
    steps: [
      { heading: '1. Acusar alertas y tomar orden', detail: 'En Taller Biomédico, acuse recibo de las alertas rojas de guardia y pulse "Tomar Orden de Trabajo".' },
      { heading: '2. Diagnosticar y registrar refacciones', detail: 'Escriba su diagnóstico técnico (visible para todo el taller), las refacciones usadas y su costo. Puede guardar notas o pausar en "Espera de Refacción".' },
      { heading: '3. Enviar a Calibración y Firmar (Firma 1)', detail: 'Envíe el equipo a Prueba Metrológica, ingrese el resultado y reingrese su contraseña institucional para emitir el Folio BioTrack (CAL-YYYY-XXXXX).' },
    ],
    tip: 'En "Equipos y Preventivos" puede ver los mantenimientos próximos a vencer (≤ 15 días) o realizar inspecciones rápidas.',
  },
  {
    role: 'JEFE_TALLER',
    title: 'Jefe de Taller',
    subtitle: 'Supervisión, escalamientos, guardias y baja definitiva',
    icon: 'bi-person-badge-fill',
    steps: [
      { heading: '1. Supervisar alertas escaladas', detail: 'Si un biomédico de guardia no acusa una falla crítica dentro del tiempo SLA, el sistema le escala la alerta automáticamente.' },
      { heading: '2. Administrar el Rol de Guardias', detail: 'En la pestaña "Guardias" programe o active a los especialistas responsables por turno.' },
      { heading: '3. Dictaminar Baja Definitiva', detail: 'Solo el Jefe de Taller puede marcar un equipo irreparable como "Baja Definitiva" desde el Taller Biomédico.' },
    ],
    tip: 'También puede consultar los 5 indicadores directivos y el expediente de auditoría SHA-256.',
  },
  {
    role: 'RESPONSABLE_AREA',
    title: 'Responsable de Área',
    subtitle: 'Doble Validación (Firma 2) y Etiqueta QR',
    icon: 'bi-patch-check-fill',
    steps: [
      { heading: '1. Revisar equipos certificados', detail: 'Entre a "Recepción (Firma 2)" para ver los equipos que Biomédica ya reparó y certificó con Firma 1.' },
      { heading: '2. Inspeccionar físicamente y firmar (Firma 2)', detail: 'Verifique el equipo en piso, pulse "Confirmar Recepción Física" e ingrese su contraseña institucional.' },
      { heading: '3. Imprimir Etiqueta Física QR', detail: 'Al confirmar, el equipo regresa a estado OPERATIVO y aparece la calcomanía con Folio y código QR público lista para imprimir.' },
    ],
    tip: 'Si escribe una contraseña incorrecta, el sistema le avisará "Firma incorrecta" y no liberará el equipo.',
  },
  {
    role: 'DIRECCION',
    title: 'Dirección Médica',
    subtitle: 'Cuadro de Mando con los 5 Indicadores Ejecutivos',
    icon: 'bi-graph-up-arrow',
    steps: [
      { heading: '1. Revisar disponibilidad y MTTR', detail: 'Consulte en "Indicadores" el porcentaje de equipos operativos por área y el tiempo promedio de reingreso.' },
      { heading: '2. Detectar equipos con fallas recurrentes', detail: 'Revise la gráfica de mayor recurrencia y el semáforo de cumplimiento del programa preventivo.' },
      { heading: '3. Evaluar reemplazo (Capex)', detail: 'En la tabla inferior compare el costo acumulado de refacciones contra el valor de reposición para justificar compras de reemplazo.' },
    ],
    tip: 'Los equipos marcados en rojo como REEMPLAZO URGENTE superan el umbral crítico de costo o tiempo fuera de servicio.',
  },
  {
    role: 'AUDITOR',
    title: 'Auditor COFEPRIS',
    subtitle: 'Verificación de expediente y cadena SHA-256 (Solo Lectura)',
    icon: 'bi-shield-lock-fill',
    steps: [
      { heading: '1. Buscar equipo por serie o código', detail: 'En "Auditoría SHA-256" escriba el número de serie o código de inventario del equipo a inspeccionar.' },
      { heading: '2. Verificar integridad criptográfica', detail: 'Compruebe el banner verde de cadena íntegra o pulse "Re-verificar SHA-256" para recalcular cada huella.' },
      { heading: '3. Explorar la línea del tiempo', detail: 'Haga clic en cada nodo de la línea del tiempo para ver claramente el usuario, fecha/hora exacta, detalles (payload) y hash SHA-256 de cada acción.' },
    ],
    tip: 'Ningún usuario puede modificar ni borrar eventos históricos gracias a los candados criptográficos y triggers de MariaDB.',
  },
]

const currentGuide = computed(() => guides.find((g) => g.role === activeRole.value) || guides[0])
</script>
