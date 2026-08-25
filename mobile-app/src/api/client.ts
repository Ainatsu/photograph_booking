import axios, { AxiosError } from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 12_000,
  headers: {
    Accept: 'application/json',
  },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401 && !String(error.config?.url || '').includes('/users/login')) {
      localStorage.removeItem('token')
      window.dispatchEvent(new CustomEvent('auth:expired'))
    }
    return Promise.reject(error)
  },
)

export function getApiErrorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    if (error.code === 'ECONNABORTED') return '连接超时，请检查后端服务或网络后重试。'
    if (!error.response) return '暂时无法连接本地服务，请确认 FastAPI 已在 8000 端口运行。'
    if (error.response.status === 401) return '登录状态已失效，请重新登录。'

    const detail = error.response.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    return `服务返回异常（${error.response.status}），请稍后重试。`
  }

  return error instanceof Error ? error.message : '加载失败，请稍后重试。'
}

export default api
