import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

import LoginView from '../views/LoginView.vue'
import FloorTerminalView from '../views/FloorTerminalView.vue'
import AssetsView from '../views/AssetsView.vue'
import WorkshopView from '../views/WorkshopView.vue'
import ReceptionView from '../views/ReceptionView.vue'
import OnCallRosterView from '../views/OnCallRosterView.vue'
import DashboardView from '../views/DashboardView.vue'
import AuditView from '../views/AuditView.vue'
import PublicVerifyView from '../views/PublicVerifyView.vue'

const routes = [
  { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
  { path: '/verify/:token', name: 'public-verify', component: PublicVerifyView, meta: { public: true } },
  { path: '/', redirect: '/floor' },
  { path: '/floor', name: 'floor', component: FloorTerminalView },
  { path: '/assets', name: 'assets', component: AssetsView },
  { path: '/workshop', name: 'workshop', component: WorkshopView },
  { path: '/reception', name: 'reception', component: ReceptionView },
  { path: '/oncall', name: 'oncall', component: OnCallRosterView },
  { path: '/dashboard', name: 'dashboard', component: DashboardView },
  { path: '/audit', name: 'audit', component: AuditView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return defaultHomeForRole(auth.role)
  }
})

export function defaultHomeForRole(role) {
  switch (role) {
    case 'CLINICO':
      return '/floor'
    case 'BIOMEDICO':
    case 'JEFE_TALLER':
      return '/workshop'
    case 'RESPONSABLE_AREA':
      return '/reception'
    case 'DIRECCION':
      return '/dashboard'
    case 'AUDITOR':
      return '/audit'
    default:
      return '/floor'
  }
}

export default router
