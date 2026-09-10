<template>
  <ion-page>
    <DetailHeader title="创建账号" default-href="/login" />

    <ion-content class="auth-content">
      <main class="auth-shell">
        <section class="auth-intro">
          <span class="auth-mark" aria-hidden="true"><UserPlus :size="25" /></span>
          <div>
            <p class="eyebrow">New account</p>
            <h1>先建立一个客户账号</h1>
            <p>注册后即可预约、发布企划和管理订单；摄影师身份可在完成作品资料后申请。</p>
          </div>
        </section>

        <form class="auth-form" novalidate @submit.prevent="submit">
          <label class="field-label" for="register-username">用户名 <span>必填</span></label>
          <input
            id="register-username"
            v-model.trim="form.username"
            class="text-field"
            type="text"
            autocomplete="username"
            autocapitalize="none"
            minlength="4"
            maxlength="24"
            placeholder="4–24 位字母、数字或下划线"
            :aria-invalid="Boolean(errors.username)"
            @blur="validateUsernameAvailability"
          />
          <p v-if="checkingUsername" class="field-hint">正在检查用户名…</p>
          <p v-else-if="usernameHint" class="field-hint" :class="{ error: Boolean(errors.username) }">
            {{ usernameHint }}
          </p>

          <label class="field-label" for="register-name">昵称 <span>必填</span></label>
          <input
            id="register-name"
            v-model.trim="form.display_name"
            class="text-field"
            type="text"
            autocomplete="name"
            maxlength="100"
            placeholder="其他用户看到的名称"
            :aria-invalid="Boolean(errors.display_name)"
            @blur="validateDisplayName"
          />
          <p v-if="errors.display_name" class="field-hint error" role="alert">{{ errors.display_name }}</p>

          <label class="field-label" for="register-email">邮箱 <span>选填</span></label>
          <input
            id="register-email"
            v-model.trim="form.email"
            class="text-field"
            type="email"
            inputmode="email"
            autocomplete="email"
            autocapitalize="none"
            placeholder="用于后续绑定和找回账号"
            :aria-invalid="Boolean(errors.email)"
            @blur="validateEmail"
          />
          <p v-if="errors.email" class="field-hint error" role="alert">{{ errors.email }}</p>

          <label class="field-label" for="register-password">密码 <span>必填</span></label>
          <div class="password-field">
            <input
              id="register-password"
              v-model="form.password"
              class="text-field"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="new-password"
              minlength="8"
              maxlength="72"
              placeholder="至少 8 个字符"
              :aria-invalid="Boolean(errors.password)"
              @blur="validatePassword"
            />
            <button type="button" class="password-toggle pressable" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
              <EyeOff v-if="showPassword" :size="19" aria-hidden="true" />
              <Eye v-else :size="19" aria-hidden="true" />
            </button>
          </div>
          <p v-if="errors.password" class="field-hint error" role="alert">{{ errors.password }}</p>

          <label class="field-label" for="register-confirm">确认密码 <span>必填</span></label>
          <input
            id="register-confirm"
            v-model="confirmPassword"
            class="text-field"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="new-password"
            placeholder="再次输入密码"
            :aria-invalid="Boolean(errors.confirmPassword)"
            @blur="validateConfirmPassword"
          />
          <p v-if="errors.confirmPassword" class="field-hint error" role="alert">{{ errors.confirmPassword }}</p>

          <div v-if="requestError" class="request-error" role="alert">
            <CircleAlert :size="18" aria-hidden="true" />
            <span>{{ requestError }}</span>
          </div>

          <button type="submit" class="submit-button pressable" :disabled="submitting || checkingUsername">
            <ion-spinner v-if="submitting" name="crescent" aria-hidden="true" />
            <span>{{ submitting ? '创建并登录中…' : '创建账号' }}</span>
          </button>
        </form>

        <p class="auth-switch">
          已有账号？
          <router-link :to="loginTarget">返回登录</router-link>
        </p>
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonContent, IonPage, IonSpinner } from '@ionic/vue'
import { CircleAlert, Eye, EyeOff, UserPlus } from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import { checkUsername } from '@/api/auth'
import { getApiErrorMessage } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const form = reactive({ username: '', display_name: '', email: '', password: '' })
const confirmPassword = ref('')
const showPassword = ref(false)
const submitting = ref(false)
const checkingUsername = ref(false)
const usernameHint = ref('注册后用户名不可修改。')
const requestError = ref('')
const errors = reactive({ username: '', display_name: '', email: '', password: '', confirmPassword: '' })
let usernameRequestId = 0

const redirectTarget = computed(() => {
  const target = String(route.query.redirect || '')
  return target.startsWith('/') && !target.startsWith('//') ? target : '/tabs/profile'
})
const loginTarget = computed(() => ({
  name: 'login',
  query: route.query.redirect ? { redirect: route.query.redirect } : undefined,
}))

/** 用请求序号丢弃过期结果：用户连续改用户名时，先发的响应可能后到。 */
async function validateUsernameAvailability() {
  const requestId = ++usernameRequestId
  const candidate = form.username
  errors.username = ''
  if (candidate.length < 4 || candidate.length > 24) {
    errors.username = '用户名需为 4–24 个字符。'
    usernameHint.value = errors.username
    return false
  }
  checkingUsername.value = true
  try {
    const result = await checkUsername(candidate)
    if (requestId !== usernameRequestId || form.username !== candidate) return false
    if (!result.available) {
      errors.username = result.reason || '该用户名已被使用。'
      usernameHint.value = errors.username
      return false
    }
    form.username = result.normalized_username
    usernameHint.value = '用户名可用。'
    return true
  } catch (error) {
    if (requestId !== usernameRequestId || form.username !== candidate) return false
    errors.username = getApiErrorMessage(error)
    usernameHint.value = errors.username
    return false
  } finally {
    if (requestId === usernameRequestId) checkingUsername.value = false
  }
}

function validateDisplayName() {
  errors.display_name = form.display_name ? '' : '请输入昵称。'
  return !errors.display_name
}

function validateEmail() {
  errors.email = form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)
    ? '请输入有效邮箱地址。'
    : ''
  return !errors.email
}

function validatePassword() {
  errors.password = form.password.length < 8 ? '密码至少需要 8 个字符。' : ''
  return !errors.password
}

function validateConfirmPassword() {
  errors.confirmPassword = confirmPassword.value !== form.password ? '两次输入的密码不一致。' : ''
  return !errors.confirmPassword
}

async function submit() {
  requestError.value = ''
  const usernameValid = await validateUsernameAvailability()
  const valid = [
    usernameValid,
    validateDisplayName(),
    validateEmail(),
    validatePassword(),
    validateConfirmPassword(),
  ].every(Boolean)
  if (!valid) return

  submitting.value = true
  try {
    await auth.register({
      username: form.username,
      display_name: form.display_name,
      email: form.email || undefined,
      password: form.password,
    })
    await router.replace(redirectTarget.value)
  } catch (error) {
    requestError.value = getApiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.auth-content {
  --background: var(--paper);
}

.auth-shell {
  width: min(100%, 520px);
  margin: 0 auto;
  padding: var(--space-5) var(--space-4) var(--space-8);
}

.auth-intro {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-5);
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--brand-soft);
}

.auth-mark {
  display: grid;
  width: 48px;
  height: 48px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: var(--radius-pill);
  background: var(--brand);
  color: var(--on-brand);
}

/* 拉丁大写短语用少量正字距；中文仍保持 0，见 DESIGN.md §4 */
.eyebrow {
  margin: 0 0 4px;
  color: var(--brand);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.auth-intro h1 {
  margin: 0 0 var(--space-2);
  font-size: var(--text-xl);
  font-weight: 700;
  line-height: var(--leading-snug);
}

.auth-intro p {
  margin: 0;
  color: var(--ink-secondary);
  font-size: var(--text-sm);
  line-height: 1.65;
}

.auth-form {
  display: grid;
  gap: var(--space-2);
  margin-top: var(--space-6);
}

.field-label {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-top: var(--space-3);
  color: var(--ink);
  font-size: var(--text-sm);
  font-weight: 700;
}

/* 「必填 / 选填」是补充说明，不与字段名争主次 */
.field-label span {
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
  font-weight: 400;
}

.text-field {
  width: 100%;
  min-height: var(--touch-target);
  padding: 0 var(--space-4);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-tertiary);
  color: var(--ink);
  font-size: var(--text-base);
  outline: none;
}

.text-field:focus {
  outline: 3px solid var(--focus-ring);
  outline-offset: 2px;
}

.text-field[aria-invalid='true'] {
  border-color: var(--danger);
}

.field-hint {
  margin: 0;
  color: var(--ink-secondary);
  font-size: var(--text-xs);
  line-height: 1.5;
}

.field-hint.error {
  color: var(--danger);
}

.password-field {
  position: relative;
}

.password-field .text-field {
  padding-right: 58px;
}

.password-toggle {
  position: absolute;
  top: 0;
  right: 3px;
  display: grid;
  width: var(--touch-target);
  height: var(--touch-target);
  place-items: center;
  border: 0;
  background: transparent;
  color: var(--ink-secondary);
}

.request-error {
  display: flex;
  gap: var(--space-2);
  align-items: flex-start;
  margin-top: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--danger);
  border-radius: var(--radius-md);
  background: var(--danger-soft);
  color: var(--danger);
  font-size: var(--text-sm);
  line-height: 1.55;
}

.request-error svg {
  flex: 0 0 auto;
  margin-top: 1px;
}

.submit-button {
  display: flex;
  min-height: var(--touch-target);
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  margin-top: var(--space-4);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--brand);
  color: var(--on-brand);
  font-weight: 700;
}

.submit-button:disabled {
  opacity: 0.55;
}

.submit-button ion-spinner {
  width: 20px;
  height: 20px;
}

.auth-switch {
  margin: var(--space-5) 0 0;
  color: var(--ink-secondary);
  font-size: var(--text-sm);
  text-align: center;
}

.auth-switch a {
  color: var(--brand);
  font-weight: 700;
  text-decoration: none;
}
</style>
