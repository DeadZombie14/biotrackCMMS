<template>
  <div class="min-vh-100 d-flex flex-column">
    <Navbar v-if="auth.isAuthenticated && !isPublicRoute" />
    <main class="flex-grow-1">
      <router-view />
    </main>
    <footer v-if="auth.isAuthenticated && !isPublicRoute" class="bg-white border-top py-2 px-3 text-muted small d-flex justify-content-between">
      <span><i class="bi bi-hospital me-1"></i> {{ auth.hospital?.name || 'BioTrack CMMS' }}</span>
      <span>NOM-016-SSA3-2012 · NOM-240-SSA1-2012 · NOM-241-SSA1-2025 · NOM-151-SCFI-2016</span>
    </footer>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useAlertsStore } from './stores/alerts'
import Navbar from './components/Navbar.vue'

const route = useRoute()
const auth = useAuthStore()
const alerts = useAlertsStore()

const isPublicRoute = computed(() => Boolean(route.meta.public))

watch(
  () => auth.isAuthenticated,
  (loggedIn) => {
    if (loggedIn) {
      auth.fetchAreas()
      alerts.fetchAlerts()
      alerts.connectStream()
    } else {
      alerts.disconnectStream()
    }
  },
  { immediate: true }
)

onMounted(() => {
  if (auth.isAuthenticated) {
    auth.fetchAreas()
    alerts.fetchAlerts()
    alerts.connectStream()
  }
})

onUnmounted(() => {
  alerts.disconnectStream()
})
</script>
