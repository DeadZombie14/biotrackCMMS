<template>
  <nav class="navbar navbar-expand-lg navbar-dark navbar-biotrack shadow-sm sticky-top">
    <div class="container-fluid">
      <router-link class="navbar-brand fw-bold d-flex align-items-center gap-2" to="/">
        <i class="bi bi-heart-pulse-fill text-info fs-4"></i>
        <span>Hospital BioTrack <span class="badge bg-info text-dark ms-1">CMMS</span></span>
      </router-link>

      <button
        class="navbar-toggler"
        type="button"
        data-bs-toggle="collapse"
        data-bs-target="#biotrackNav"
      >
        <span class="navbar-toggler-icon"></span>
      </button>

      <div class="collapse navbar-collapse" id="biotrackNav">
        <ul class="navbar-nav me-auto mb-2 mb-lg-0">
          <li class="nav-item" v-if="can(['CLINICO', 'RESPONSABLE_AREA', 'BIOMEDICO', 'JEFE_TALLER'])">
            <router-link class="nav-link" active-class="active fw-semibold" to="/floor">
              <i class="bi bi-exclamation-octagon me-1"></i> Terminal de Piso
            </router-link>
          </li>
          <li class="nav-item" v-if="can(['BIOMEDICO', 'JEFE_TALLER'])">
            <router-link class="nav-link" active-class="active fw-semibold" to="/workshop">
              <i class="bi bi-wrench-adjustable-circle me-1"></i> Taller Biomédico
              <span v-if="alerts.pendingAlerts.length" class="badge bg-danger ms-1">
                {{ alerts.pendingAlerts.length }}
              </span>
            </router-link>
          </li>
          <li class="nav-item" v-if="can(['RESPONSABLE_AREA', 'JEFE_TALLER'])">
            <router-link class="nav-link" active-class="active fw-semibold" to="/reception">
              <i class="bi bi-patch-check me-1"></i> Recepción (Firma 2)
            </router-link>
          </li>
          <li class="nav-item">
            <router-link class="nav-link" active-class="active fw-semibold" to="/assets">
              <i class="bi bi-cpu me-1"></i> Equipos y Preventivos
            </router-link>
          </li>
          <li class="nav-item" v-if="can(['BIOMEDICO', 'JEFE_TALLER'])">
            <router-link class="nav-link" active-class="active fw-semibold" to="/oncall">
              <i class="bi bi-telephone-inbound me-1"></i> Guardias
            </router-link>
          </li>
          <li class="nav-item" v-if="can(['DIRECCION', 'JEFE_TALLER', 'AUDITOR', 'BIOMEDICO'])">
            <router-link class="nav-link" active-class="active fw-semibold" to="/dashboard">
              <i class="bi bi-graph-up-arrow me-1"></i> Indicadores
            </router-link>
          </li>
          <li class="nav-item" v-if="can(['AUDITOR', 'DIRECCION', 'JEFE_TALLER'])">
            <router-link class="nav-link" active-class="active fw-semibold" to="/audit">
              <i class="bi bi-shield-lock me-1"></i> Auditoría SHA-256
            </router-link>
          </li>
        </ul>

        <div class="d-flex align-items-center gap-2 text-white small">
          <button
            type="button"
            class="btn btn-info btn-sm text-dark fw-semibold"
            @click="showGuide = true"
          >
            <i class="bi bi-question-circle-fill me-1"></i>Guía de Uso
          </button>
          <div class="text-end d-none d-md-block ms-2">
            <div class="fw-semibold">{{ auth.user?.full_name }}</div>
            <span class="badge bg-light text-dark">{{ roleLabel(auth.role) }}</span>
          </div>
          <button class="btn btn-outline-light btn-sm" @click="doLogout">
            <i class="bi bi-box-arrow-right me-1"></i> Salir
          </button>
        </div>
      </div>
    </div>
  </nav>

  <RoleGuideModal :visible="showGuide" :currentRole="auth.role" @close="showGuide = false" />
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useAlertsStore } from '../stores/alerts'
import RoleGuideModal from './RoleGuideModal.vue'

const router = useRouter()
const auth = useAuthStore()
const alerts = useAlertsStore()
const showGuide = ref(false)

function can(roles) {
  return roles.includes(auth.role)
}

function roleLabel(role) {
  const map = {
    CLINICO: 'Personal Clínico',
    BIOMEDICO: 'Ing. Biomédico',
    JEFE_TALLER: 'Jefe de Taller',
    RESPONSABLE_AREA: 'Responsable de Área',
    DIRECCION: 'Dirección Médica',
    AUDITOR: 'Auditor COFEPRIS',
  }
  return map[role] || role
}

function doLogout() {
  auth.logout()
  router.push('/login')
}
</script>
