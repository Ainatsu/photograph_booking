import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
    baseURL: '/api/v1',
    timeout: 10000,
})

// 请求拦截器：自动附加 token
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token')
        if (token) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
    },
    (error) => Promise.reject(error)
)

// 响应拦截器：统一错误处理
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('token')
        }
        if (!error.config?.skipErrorHandler) {
            const detail = error.response?.data?.detail
            const message = typeof detail === 'object' ? (detail.message || detail.code || '请求失败') : (detail || '请求失败')
            ElMessage.error(message)
        }
        return Promise.reject(error)
    }
)

export default api
