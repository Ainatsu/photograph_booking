<template>
  <div class="page">
    <div class="card">
      <h2 class="title">注册</h2>
      <p class="subtitle">设置用户名和昵称即可创建账号，邮箱与手机号可稍后绑定</p>
      <el-form :model="form" label-position="top" class="form" @submit.prevent="handleRegister">
        <el-form-item label="用户名" required :error="errors.username" class="form-item">
          <el-input
            v-model="form.username"
            aria-label="用户名"
            autocomplete="username"
            placeholder="4-24 位字母、数字或下划线"
            class="input"
            @blur="checkUsername"
          />
          <span v-if="usernameHint" class="helper" :class="{ success: usernameAvailable }" aria-live="polite">
            {{ usernameHint }}
          </span>
        </el-form-item>

        <el-form-item label="手机号（可选）" :error="errors.phone" class="form-item">
          <el-input
            v-model="form.phone"
            type="tel"
            aria-label="手机号"
            autocomplete="tel"
            placeholder="请输入手机号"
            class="input"
          />
        </el-form-item>

        <el-form-item v-if="normalizedPhone" label="短信验证码" required :error="errors.code" class="form-item">
          <div class="code-row">
            <el-input
              v-model="form.code"
              type="number"
              aria-label="短信验证码"
              inputmode="numeric"
              autocomplete="one-time-code"
              placeholder="6 位验证码"
              class="input"
            />
            <el-button class="code-btn" :disabled="countdown > 0 || sendingCode" @click="sendCode">
              {{ countdown > 0 ? `${countdown}s 后重发` : sendingCode ? '发送中…' : '获取验证码' }}
            </el-button>
          </div>
          <span class="helper">验证码 5 分钟内有效，每 60 秒可重新发送。</span>
        </el-form-item>

        <el-form-item label="昵称" required :error="errors.display_name" class="form-item">
          <el-input v-model="form.display_name" aria-label="昵称" autocomplete="nickname" placeholder="请输入昵称" class="input" />
        </el-form-item>

        <el-form-item label="邮箱（可选）" :error="errors.email" class="form-item">
          <el-input v-model="form.email" type="email" aria-label="邮箱（可选）" autocomplete="email" placeholder="验证后可用于登录" class="input" />
        </el-form-item>

        <el-form-item label="密码" required :error="errors.password" class="form-item">
          <el-input v-model="form.password" type="password" show-password aria-label="密码" autocomplete="new-password" placeholder="至少 8 个字符" class="input" />
        </el-form-item>

        <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
        <el-button native-type="submit" type="primary" class="btn" :loading="submitting" :disabled="submitting">
          {{ submitting ? '注册中…' : '注册' }}
        </el-button>
      </el-form>
      <p class="tip">已有账号？<router-link to="/login" class="link">去登录</router-link></p>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import auth from '../api/auth'
import api from '../utils/api'

const router = useRouter()
const form = ref({ username: '', phone: '', code: '', challenge_id: '', display_name: '', email: '', password: '' })
const errors = ref({})
const formError = ref('')
const usernameAvailable = ref(false)
const usernameHint = ref('')
const submitting = ref(false)
const sendingCode = ref(false)
const countdown = ref(0)
let timer

const normalizedPhone = computed(() => form.value.phone.trim())

const validateUsername = () => {
  const value = form.value.username.trim().toLowerCase().replace(/^@/, '')
  form.value.username = value
  if (!/^[a-z][a-z0-9_]{3,23}$/.test(value)) {
    errors.value.username = '用户名需为 4-24 位，以字母开头，只能包含字母、数字和下划线。'
    usernameAvailable.value = false
    usernameHint.value = ''
    return false
  }
  return true
}

const checkUsername = async () => {
  if (!validateUsername()) return
  try {
    const { data } = await auth.checkUsernameAvailability(form.value.username)
    usernameAvailable.value = data.available
    usernameHint.value = data.available ? '这个用户名可以使用，注册后不可修改。' : '这个用户名已被占用。'
    if (!data.available) errors.value.username = '用户名已被占用，请换一个。'
    else delete errors.value.username
  } catch {
    usernameHint.value = '暂时无法检查占用情况，提交时会再次校验。'
  }
}

const sendCode = async () => {
  errors.value.phone = ''
  if (!normalizedPhone.value) {
    errors.value.phone = '请输入手机号。'
    return
  }
  sendingCode.value = true
  formError.value = ''
  try {
    const { data } = await auth.requestVerification({ channel: 'phone', target: normalizedPhone.value, purpose: 'register' })
    form.value.challenge_id = data.challenge_id
    countdown.value = 60
    timer = window.setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) window.clearInterval(timer)
    }, 1000)
  } catch (error) {
    formError.value = error.response?.data?.detail || '验证码发送失败，请稍后重试。'
  } finally {
    sendingCode.value = false
  }
}

const validate = () => {
  errors.value = {}
  const validUsername = validateUsername()
  if (!validUsername) return false
  if (normalizedPhone.value && !/^\d{6}$/.test(form.value.code)) errors.value.code = '请输入 6 位短信验证码。'
  if (!form.value.display_name.trim()) errors.value.display_name = '请输入昵称。'
  if (form.value.email && !/^\S+@\S+\.\S+$/.test(form.value.email.trim())) errors.value.email = '邮箱格式不正确。'
  if (form.value.password.length < 8) errors.value.password = '密码至少需要 8 个字符。'
  return Object.keys(errors.value).length === 0
}

const handleRegister = async () => {
  formError.value = ''
  if (!validate()) return
  submitting.value = true
  try {
    let phoneVerificationToken
    if (normalizedPhone.value) {
      const { data } = await auth.confirmVerification({ challenge_id: form.value.challenge_id, code: form.value.code })
      phoneVerificationToken = data.verification_token
    }
    await api.post('/users/register', {
      username: form.value.username,
      phone_verification_token: phoneVerificationToken,
      email: form.value.email.trim() || undefined,
      password: form.value.password,
      display_name: form.value.display_name.trim(),
    })
    router.push('/login')
  } catch (error) {
    formError.value = error.response?.data?.detail || '注册失败，请检查信息后重试。'
  } finally {
    submitting.value = false
  }
}

onBeforeUnmount(() => timer && window.clearInterval(timer))
</script>

<style scoped>
.page { display: flex; justify-content: center; align-items: center; min-height: 100dvh; padding: var(--space-4); background: var(--color-paper); }
.card { width: 100%; max-width: 480px; padding: var(--space-8); background: var(--color-paper-light); border: var(--border-default); border-radius: var(--radius-lg); }
.title { margin: 0; color: var(--color-ink); text-align: center; font-size: var(--text-2xl); }
.subtitle { margin: var(--space-2) 0 var(--space-6); color: var(--color-ink-secondary); text-align: center; font-size: var(--text-sm); }
.form { display: flex; flex-direction: column; gap: var(--space-3); width: 100%; }
.form-item { width: 100%; margin-bottom: 0; }
.form-item :deep(.el-form-item__label) { justify-content: flex-start; width: 100%; height: auto; margin-bottom: var(--space-1); padding: 0; color: var(--color-ink-secondary); font-size: var(--text-sm); line-height: var(--leading-relaxed); }
.form-item :deep(.el-form-item__content) { display: block; width: 100%; line-height: normal; }
.form-item :deep(.el-form-item__error) { position: static; padding-top: var(--space-1); line-height: 1.5; }
.input { width: 100%; min-width: 0; }
.input :deep(.el-input__wrapper) { min-height: var(--tap-target-min); background: var(--color-paper-light); border: var(--border-default); border-radius: var(--radius-md); box-shadow: none; }
.input :deep(.el-input__inner) { color: var(--color-ink); font-size: var(--text-base); }
.code-row { display: grid; grid-template-columns: minmax(0, 1fr) 120px; gap: var(--space-2); width: 100%; }
.code-btn { width: 100%; min-width: 0; min-height: var(--tap-target-min); white-space: nowrap; }
.helper { display: block; margin-top: 4px; color: var(--color-ink-tertiary); font-size: var(--text-xs); line-height: 1.5; }
.helper.success { color: var(--color-success, #16794c); }
.form-error { margin: 0; color: var(--color-danger, #b42318); font-size: var(--text-sm); }
.btn { width: 100%; min-height: var(--tap-target-min); margin-top: var(--space-2); border-radius: var(--radius-md); }
.tip { margin: var(--space-4) 0 0; color: var(--color-ink-secondary); text-align: center; font-size: var(--text-sm); }
.link { color: var(--color-brand); font-weight: 600; }
@media (max-width: 480px) { .card { padding: var(--space-6); } }
@media (max-width: 400px) { .code-row { grid-template-columns: 1fr; } }
</style>
