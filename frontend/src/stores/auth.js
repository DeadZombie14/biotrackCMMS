import { defineStore } from 'pinia'
import api from '../services/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('biotrack_token') || null,
    user: JSON.parse(localStorage.getItem('biotrack_user') || 'null'),
    hospital: JSON.parse(localStorage.getItem('biotrack_hospital') || 'null'),
    terminalAreaId: Number(localStorage.getItem('biotrack_terminal_area_id')) || null,
    areas: [],
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token && state.user),
    role: (state) => state.user?.role || null,
  },
  actions: {
    async login(email, password) {
      const { data } = await api.post('/auth/login', { email, password })
      this.token = data.access_token
      this.user = data.user
      this.hospital = data.hospital
      localStorage.setItem('biotrack_token', data.access_token)
      localStorage.setItem('biotrack_user', JSON.stringify(data.user))
      localStorage.setItem('biotrack_hospital', JSON.stringify(data.hospital))
      if (data.user.area_id && !this.terminalAreaId) {
        this.setTerminalArea(data.user.area_id)
      }
      await this.fetchAreas()
      return data.user
    },
    async fetchAreas() {
      if (!this.token) return
      const { data } = await api.get('/auth/areas')
      this.areas = data.areas || []
      if (!this.terminalAreaId && this.areas.length > 0) {
        this.setTerminalArea(this.user?.area_id || this.areas[0].id)
      }
    },
    setTerminalArea(areaId) {
      this.terminalAreaId = Number(areaId)
      localStorage.setItem('biotrack_terminal_area_id', String(areaId))
    },
    logout() {
      this.token = null
      this.user = null
      this.hospital = null
      localStorage.removeItem('biotrack_token')
      localStorage.removeItem('biotrack_user')
      localStorage.removeItem('biotrack_hospital')
    },
  },
})
