<template>
  <div class="page">
    <div class="card">
      <h2 class="title">登录</h2>
      <p class="subtitle">支持用户名、已验证邮箱或已验证手机号</p>
      <el-form :model="form" class="form" @submit.prevent="handleLogin">
        <el-form-item label="账号" required :error="error" class="form-item">
          <el-input v-model="form.username" aria-label="用户名、邮箱或手机号" autocomplete="username" placeholder="用户名 / 邮箱 / 手机号" class="input" />
        </el-form-item>
        <el-form-item label="密码" required class="form-item">
          <el-input v-model="form.password" type="password" show-password aria-label="密码" autocomplete="current-password" placeholder="请输入密码" class="input" />
        </el-form-item>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <el-button native-type="submit" type="primary" class="btn" :loading="submitting" :disabled="submitting">
          {{ submitting ? '登录中…' : '登录' }}
        </el-button>
      </el-form>
      <p class="tip">还没有账号？<router-link to="/register" class="link">去注册</router-link></p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../utils/api'

const router = useRouter()
const form = ref({ username: '', password: '' })
const error = ref('')
const submitting = ref(false)

const handleLogin = async () => {
  error.value = ''
  if (!form.value.username.trim() || !form.value.password) {
    error.value = '请输入账号和密码。'
    return
  }
  submitting.value = true
  try {
    const params = new URLSearchParams()
    params.append('username', form.value.username.trim())
    params.append('password', form.value.password)
    const res = await api.post('/users/login', params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    localStorage.setItem('token', res.data.access_token)
    router.push('/')
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || '账号或密码错误，请重试。'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.page { display: flex; justify-content: center; align-items: center; min-height: 100dvh; padding: var(--space-4); background: var(--color-paper); }
.card { width: 100%; max-width: 420px; padding: var(--space-8); background: var(--color-paper-light); border: var(--border-default); border-radius: var(--radius-lg); }
.title { margin: 0; color: var(--color-ink); text-align: center; font-size: var(--text-2xl); }
.subtitle { margin: var(--space-2) 0 var(--space-6); color: var(--color-ink-secondary); text-align: center; font-size: var(--text-sm); }
.form { display: flex; flex-direction: column; gap: var(--space-3); }
.form-item { margin-bottom: 0; }
.form-item :deep(.el-form-item__label) { color: var(--color-ink-secondary); font-size: var(--text-sm); }
.input :deep(.el-input__wrapper) { min-height: var(--tap-target-min); background: var(--color-paper-light); border: var(--border-default); border-radius: var(--radius-md); box-shadow: none; }
.input :deep(.el-input__inner) { color: var(--color-ink); font-size: var(--text-base); }
.form-error { margin: 0; color: var(--color-danger, #b42318); font-size: var(--text-sm); }
.btn { width: 100%; min-height: var(--tap-target-min); margin-top: var(--space-2); border-radius: var(--radius-md); }
.tip { margin: var(--space-4) 0 0; color: var(--color-ink-secondary); text-align: center; font-size: var(--text-sm); }
.link { color: var(--color-brand); font-weight: 600; }
</style>
