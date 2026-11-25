<template>
  <span :class="['badge', badgeClass]">
    <i :class="['bi me-1', iconClass]"></i>{{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  state: { type: String, required: true },
})

const config = computed(() => {
  const map = {
    OPERATIVO: { cls: 'bg-success', icon: 'bi-check-circle-fill', label: 'Operativo' },
    REPORTADO: { cls: 'bg-warning text-dark', icon: 'bi-exclamation-triangle-fill', label: 'Reportado' },
    BLOQUEADO: { cls: 'bg-danger', icon: 'bi-slash-circle-fill', label: 'BLOQUEADO (Fail-Safe)' },
    EN_MANTENIMIENTO_PREVENTIVO: { cls: 'bg-info text-dark', icon: 'bi-calendar-check', label: 'Preventivo' },
    EN_DIAGNOSTICO: { cls: 'bg-warning text-dark', icon: 'bi-search', label: 'En Diagnóstico' },
    EN_ESPERA_REFACCION: { cls: 'bg-secondary', icon: 'bi-hourglass-split', label: 'Espera Refacción' },
    EN_CALIBRACION: { cls: 'bg-primary', icon: 'bi-sliders', label: 'En Calibración' },
    CERTIFICADO_PENDIENTE_RECEPCION: { cls: 'bg-info text-dark', icon: 'bi-pen-fill', label: 'Pendiente Firma 2' },
    BAJA_DEFINITIVA: { cls: 'bg-dark', icon: 'bi-x-octagon-fill', label: 'Baja Definitiva' },
  }
  return map[props.state] || { cls: 'bg-secondary', icon: 'bi-question-circle', label: props.state }
})

const badgeClass = computed(() => config.value.cls)
const iconClass = computed(() => config.value.icon)
const label = computed(() => config.value.label)
</script>
