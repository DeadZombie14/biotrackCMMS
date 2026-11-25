import { defineStore } from 'pinia'
import api from '../services/api'

function playAlarmTone() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext
    if (!AudioCtx) return
    const ctx = new AudioCtx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sawtooth'
    osc.frequency.setValueAtTime(880, ctx.currentTime)
    osc.frequency.setValueAtTime(660, ctx.currentTime + 0.18)
    osc.frequency.setValueAtTime(880, ctx.currentTime + 0.36)
    gain.gain.setValueAtTime(0.12, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6)
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.6)
  } catch (_) {
    // Browser autoplay policy may block audio before user interaction
  }
}

export const useAlertsStore = defineStore('alerts', {
  state: () => ({
    alerts: [],
    lastCriticalEvent: null,
    eventSource: null,
    soundEnabled: true,
  }),
  getters: {
    pendingAlerts: (state) => state.alerts.filter((a) => a.status === 'PENDIENTE' || a.status === 'ESCALADO'),
  },
  actions: {
    async fetchAlerts() {
      try {
        const { data } = await api.get('/alerts')
        this.alerts = data.alerts || []
      } catch (_) {
        // Ignore if not logged in
      }
    },
    connectStream() {
      if (this.eventSource) return
      const es = new EventSource('/api/v1/alerts/stream')
      es.addEventListener('critical_block', (ev) => {
        const payload = JSON.parse(ev.data)
        this.lastCriticalEvent = payload
        this.alerts.unshift(payload)
        if (this.soundEnabled) playAlarmTone()
      })
      es.addEventListener('alert_escalated', (ev) => {
        const payload = JSON.parse(ev.data)
        this.lastCriticalEvent = payload
        this.fetchAlerts()
        if (this.soundEnabled) playAlarmTone()
      })
      es.addEventListener('alert_acknowledged', () => {
        this.fetchAlerts()
      })
      this.eventSource = es
    },
    disconnectStream() {
      if (this.eventSource) {
        this.eventSource.close()
        this.eventSource = null
      }
    },
    async acknowledge(alertId) {
      await api.post(`/alerts/${alertId}/ack`)
      await this.fetchAlerts()
    },
    async checkEscalations() {
      const { data } = await api.post('/alerts/check-escalations')
      await this.fetchAlerts()
      return data
    },
  },
})
