/**
 * api.spec.js — API 工具层单元测试
 * 测试：Axios 实例配置、请求/响应拦截器
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'
import api from '../../utils/api'

describe('API Utility', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('should create axios instance with correct baseURL', () => {
    expect(api.defaults.baseURL).toBe('/api/v1')
  })

  it('should have correct timeout', () => {
    expect(api.defaults.timeout).toBe(10000)
  })

  it('should attach token from localStorage in request interceptor', async () => {
    localStorage.setItem('token', 'test-jwt-token')

    const config = { headers: {} }
    const interceptor = api.interceptors.request.handlers[0]
    const result = interceptor.fulfilled(config)

    expect(result.headers.Authorization).toBe('Bearer test-jwt-token')
  })

  it('should not attach Authorization when no token', async () => {
    const config = { headers: {} }
    const interceptor = api.interceptors.request.handlers[0]
    const result = interceptor.fulfilled(config)

    expect(result.headers.Authorization).toBeUndefined()
  })

  it('should pass through request errors', async () => {
    const error = new Error('Request Error')
    const interceptor = api.interceptors.request.handlers[0]

    try {
      await interceptor.rejected(error)
      expect.fail('Should have thrown')
    } catch (e) {
      expect(e).toBe(error)
    }
  })

  it('should pass through successful responses', () => {
    const response = { data: { message: 'ok' }, status: 200 }
    const interceptor = api.interceptors.response.handlers[0]
    const result = interceptor.fulfilled(response)

    expect(result).toBe(response)
  })

  it('should handle response errors with detail', async () => {
    const error = {
      response: { data: { detail: '资源不存在' }, status: 404 },
      config: {},
    }
    const interceptor = api.interceptors.response.handlers[0]

    try {
      await interceptor.rejected(error)
    } catch (e) {
      expect(e).toBe(error)
    }
  })

  it('should handle errors with skipErrorHandler flag', async () => {
    const error = {
      response: { data: { detail: '错误' }, status: 400 },
      config: { skipErrorHandler: true },
    }
    const interceptor = api.interceptors.response.handlers[0]

    try {
      await interceptor.rejected(error)
    } catch (e) {
      expect(e).toBe(error)
    }
  })

  it('should clear token on unauthorized responses', async () => {
    localStorage.setItem('token', 'stale-token')
    const error = {
      response: { data: { detail: 'Unauthorized' }, status: 401 },
      config: { skipErrorHandler: true },
    }
    const interceptor = api.interceptors.response.handlers[0]

    try {
      await interceptor.rejected(error)
    } catch (e) {
      expect(e).toBe(error)
      expect(localStorage.getItem('token')).toBeNull()
    }
  })

  it('should handle network errors without response', async () => {
    const error = { message: 'Network Error', config: {} }
    const interceptor = api.interceptors.response.handlers[0]

    try {
      await interceptor.rejected(error)
    } catch (e) {
      expect(e).toBe(error)
    }
  })

  it('should update token on subsequent requests', () => {
    localStorage.setItem('token', 'first-token')
    const interceptor = api.interceptors.request.handlers[0]

    let result = interceptor.fulfilled({ headers: {} })
    expect(result.headers.Authorization).toBe('Bearer first-token')

    localStorage.setItem('token', 'second-token')
    result = interceptor.fulfilled({ headers: {} })
    expect(result.headers.Authorization).toBe('Bearer second-token')
  })
})
