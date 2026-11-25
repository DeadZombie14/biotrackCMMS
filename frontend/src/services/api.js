import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('biotrack_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401 && !error.config.url.includes('/certify') && !error.config.url.includes('/receive') && !error.config.url.includes('/login')) {
      localStorage.removeItem('biotrack_token')
      localStorage.removeItem('biotrack_user')
      if (window.location.pathname !== '/login' && !window.location.pathname.startsWith('/verify/')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
