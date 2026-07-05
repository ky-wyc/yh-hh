import axios from 'axios'
import { ElMessage } from 'element-plus'
import { clearToken, getToken } from './auth'

export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      clearToken()
      if (window.location.pathname !== '/login') {
        ElMessage.warning('登录已失效，请重新登录')
        window.location.assign('/login')
      }
    }
    return Promise.reject(error)
  }
)
