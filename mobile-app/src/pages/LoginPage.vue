<template>
  <ion-page>
    <DetailHeader title="登录" default-href="/tabs/profile" />

    <ion-content class="auth-content">
      <main class="auth-shell">
        <section class="auth-intro">
          <span class="auth-mark" aria-hidden="true"><LogIn :size="25" /></span>
          <div>
            <p class="eyebrow">Welcome back</p>
            <h1>继续你的约拍行程</h1>
            <p>登录后可预约真实档期、查看订单，并在客户与摄影师工作流之间保持数据同步。</p>
          </div>
        </section>

        <form class="auth-form" novalidate @submit.prevent="submit">
          <label class="field-label" for="login-account">账号</label>
          <input
            id="login-account"
            ref="accountInput"
            v-model.trim="account"
            class="text-field"
            name="username"
            type="text"
            autocomplete="username"
            autocapitalize="none"
            enterkeyhint="next"
            placeholder="用户名 / 已验证邮箱 / 已验证手机号"
            :aria-invalid="Boolean(fieldErrors.account)"
            :aria-describedby="fieldErrors.account ? 'login-account-error' : undefined"
            @blur="validateAccount"
          />
          <p v-if="fieldErrors.account" id="login-account-error" class="field-error" role="alert">
            {{ fieldErrors.account }}
          </p>

          <label class="field-label" for="login-password">密码</label>
          <div class="password-field">
            <input
              id="login-password"
              v-model="password"
              class="text-field"
              name="password"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
              enterkeyhint="done"
              placeholder="请输入密码"
              :aria-invalid="Boolean(fieldErrors.password)"
              :aria-describedby="fieldErrors.password ? 'login-password-error' : undefined"
              @blur="validatePassword"
            />
            <button
              type="button"
              class="password-toggle pressable"
              :aria-label="showPassword ? '隐藏密码' : '显示密码'"
              @click="showPassword = !showPassword"
            >
              <EyeOff v-if="showPassword" :size="19" aria-hidden="true" />
              <Eye v-else :size="19" aria-hidden="true" />
            </button>
          </div>
          <p v-if="fieldErrors.password" id="login-password-error" class="field-error" role="alert">
            {{ fieldErrors.password }}
          </p>

          <div v-if="requestError" class="request-error" role="alert">
            <CircleAlert :size="18" aria-hidden="true" />
            <span>{{ requestError }}</span>
          </div>

          <button type="submit" class="submit-button pressable" :disabled="submitting">
            <ion-spinner v-if="submitting" name="crescent" aria-hidden="true" />
            <span>{{ submitting ? '登录中…' : '登录' }}</span>
          </button>
        </form>

        <p class="auth-switch">
          还没有账号？
          <router-link :to="registerTarget">创建账号</router-link>
        </p>

        <section class="demo-note">
          <ShieldCheck :size="20" aria-hidden="true" />
          <p>本地演示可使用项目 README 中的客户或摄影师账号，登录信息只发送到当前配置的 FastAPI 服务。</p>
        </section>
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonContent, IonPage, IonSpinner } from '@ionic/vue'
import { CircleAlert, Eye, EyeOff, LogIn, ShieldCheck } from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import { getApiErrorMessage } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const accountInput = ref<HTMLInputElement | null>(null)
const account = ref('')
const password = ref('')
const showPassword = ref(false)
const submitting = ref(false)
const requestError = ref('')
const fieldErrors = reactive({ account: '', password: '' })

const redirectTarget = computed(() => {
  const target = String(route.query.redirect || '')
  return target.startsWith('/') && !target.startsWith('//') ? target : '/tabs/profile'
})
const registerTarget = computed(() => ({
  name: 'register',
  query: route.query.redirect ? { redirect: route.query.redirect } : undefined,
}))

function validateAccount() {
  fieldErrors.account = account.value ? '' : '请输入用户名、邮箱或手机号。'
  return !fieldErrors.account
}

function validatePassword() {
  fieldErrors.password = password.value ? '' : '请输入密码。'
  return !fieldErrors.password
}

async function submit() {
  requestError.value = ''
  if (!validateAccount() || !validatePassword()) return

  submitting.value = true
  try {
    await auth.login(account.value, password.value)
    await router.replace(redirectTarget.value)
  } catch (error) {
    requestError.value = getApiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await nextTick()
  accountInput.value?.focus()
})
</script>

<style scoped>
.auth-content { --background: var(--paper); }
.auth-shell { width: min(100%, 520px); margin: 0 auto; padding: var(--space-5) var(--space-4) var(--space-8); }
.auth-intro { display: flex; gap: var(--space-4); padding: var(--space-5); border: 0; border-radius: var(--radius-lg); background: var(--brand-soft); box-shadow: var(--neu-raise); }
.auth-mark { display: grid; width: 48px; height: 48px; flex: 0 0 auto; place-items: center; border-radius: 50%; background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); }
.eyebrow { margin: 0 0 4px !important; color: var(--brand) !important; font-size: 11px !important; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
.auth-intro h1 { margin: 0 0 var(--space-2); font-family: var(--font-serif); font-size: var(--text-xl); line-height: 1.4; }
.auth-intro p { margin: 0; color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.65; }
.auth-form { display: grid; gap: var(--space-2); margin-top: var(--space-6); }
.field-label { margin-top: var(--space-3); color: var(--ink); font-size: var(--text-sm); font-weight: 700; }
.text-field { width: 100%; min-height: var(--touch-target); padding: 0 var(--space-4); border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink); font-size: var(--text-base); outline: none; }
.text-field:focus { box-shadow: var(--neu-inset-deep), 0 0 0 2px rgba(45, 90, 39, 0.26); }
.text-field[aria-invalid="true"] { border-color: var(--danger); }
.password-field { position: relative; }
.password-field .text-field { padding-right: 58px; }
.password-toggle { position: absolute; top: 0; right: 3px; display: grid; width: var(--touch-target); height: var(--touch-target); place-items: center; border: 0; background: transparent; color: var(--ink-secondary); }
.field-error { margin: 0; color: var(--danger); font-size: var(--text-xs); line-height: 1.5; }
.request-error { display: flex; gap: var(--space-2); align-items: flex-start; margin-top: var(--space-3); padding: var(--space-3); border: 1px solid rgba(163, 59, 50, .25); border-radius: var(--radius-md); background: #fbefed; color: var(--danger); font-size: var(--text-sm); line-height: 1.55; }
.request-error svg { flex: 0 0 auto; margin-top: 1px; }
.submit-button { display: flex; min-height: var(--touch-target); align-items: center; justify-content: center; gap: var(--space-2); margin-top: var(--space-4); border: 0; border-radius: var(--radius-md); background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); font-weight: 750; }
.submit-button:disabled { opacity: .55; }
.submit-button ion-spinner { width: 20px; height: 20px; }
.auth-switch { margin: var(--space-5) 0 0; color: var(--ink-secondary); font-size: var(--text-sm); text-align: center; }
.auth-switch a { color: var(--brand); font-weight: 750; text-decoration: none; }
.demo-note { display: flex; gap: var(--space-3); margin-top: var(--space-6); padding: var(--space-4); border-top: 1px solid var(--neu-light); box-shadow: inset 0 1px 0 var(--neu-shade-soft); color: var(--brand); }
.demo-note p { margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.65; }
</style>
