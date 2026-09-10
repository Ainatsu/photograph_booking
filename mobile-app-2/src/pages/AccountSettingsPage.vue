<template>
  <ion-page>
    <DetailHeader title="资料与账号" default-href="/tabs/profile" />

    <ion-content class="account-content">
      <main class="account-shell">
        <FeedSkeleton v-if="loading" :count="3" />

        <StatePanel
          v-else-if="loadError"
          tone="error"
          title="账号资料加载失败"
          :description="loadError"
          action-label="重新加载"
          @action="loadAccount"
        />

        <template v-else-if="auth.user">
          <section class="account-summary">
            <AvatarImage :src="avatarSource" :name="auth.user.display_name" :size="64" />
            <div>
              <p>Account center</p>
              <h1>{{ auth.user.display_name }}</h1>
              <small>@{{ auth.user.username || `user-${auth.user.id}` }}</small>
            </div>
            <span class="session-badge"><ShieldCheck :size="15" aria-hidden="true" />已登录</span>
          </section>

          <SegmentSwitch
            :model-value="activeSection"
            :items="sectionItems"
            label="资料与账号设置分类"
            @update:model-value="setSection"
          />

          <form v-if="activeSection === 'profile'" class="account-form" novalidate @submit.prevent="saveProfile">
            <section class="settings-card">
              <header class="card-heading">
                <span><Images :size="20" aria-hidden="true" /></span>
                <div>
                  <h2>头像与主页封面</h2>
                  <p>图片上传后立即生效，支持 JPG、PNG、WebP，单张不超过 10 MB。</p>
                </div>
              </header>

              <div class="cover-editor">
                <div class="cover-preview" aria-label="主页封面预览">
                  <img v-if="coverSource" :src="coverSource" alt="" />
                  <div v-else class="cover-empty">
                    <ImagePlus :size="27" aria-hidden="true" />
                    <span>还没有主页封面</span>
                  </div>
                  <span v-if="uploadingImage === 'background'" class="upload-overlay" role="status">
                    <ion-spinner name="crescent" aria-hidden="true" />上传中
                  </span>
                </div>
                <button
                  type="button"
                  class="secondary-button pressable"
                  :disabled="Boolean(uploadingImage) || savingProfile"
                  :aria-busy="uploadingImage === 'background'"
                  @click="openImagePicker('background')"
                >
                  <ImagePlus :size="18" aria-hidden="true" />
                  {{ auth.user.background_url ? '更换主页封面' : '上传主页封面' }}
                </button>
              </div>

              <div class="avatar-editor">
                <div class="avatar-preview-wrap">
                  <AvatarImage :src="avatarSource" :name="profileForm.displayName || auth.user.display_name" :size="76" />
                  <span v-if="uploadingImage === 'avatar'" class="avatar-loading" role="status">
                    <ion-spinner name="crescent" aria-label="头像上传中" />
                  </span>
                </div>
                <div>
                  <strong>个人头像</strong>
                  <p>建议使用清晰的正方形图片，方便客户在订单和消息中识别你。</p>
                  <button
                    type="button"
                    class="inline-action pressable"
                    :disabled="Boolean(uploadingImage) || savingProfile"
                    :aria-busy="uploadingImage === 'avatar'"
                    @click="openImagePicker('avatar')"
                  >
                    <Camera :size="17" aria-hidden="true" />更换头像
                  </button>
                </div>
              </div>

              <input
                ref="avatarInput"
                class="sr-only"
                type="file"
                accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
                tabindex="-1"
                @change="handleImageSelection($event, 'avatar')"
              />
              <input
                ref="backgroundInput"
                class="sr-only"
                type="file"
                accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
                tabindex="-1"
                @change="handleImageSelection($event, 'background')"
              />
              <p v-if="imageError" class="field-error" role="alert">{{ imageError }}</p>
            </section>

            <section class="settings-card">
              <header class="card-heading">
                <span><UserRound :size="20" aria-hidden="true" /></span>
                <div>
                  <h2>公开资料</h2>
                  <p>昵称和简介会展示在个人主页、作品、企划与订单相关页面。</p>
                </div>
              </header>

              <div class="settings-field">
                <label for="account-display-name">昵称 <span>必填</span></label>
                <input
                  id="account-display-name"
                  v-model="profileForm.displayName"
                  class="settings-input"
                  type="text"
                  autocomplete="name"
                  maxlength="100"
                  :disabled="savingProfile"
                  :aria-invalid="Boolean(profileErrors.displayName)"
                  @blur="validateProfileName"
                />
                <p v-if="profileErrors.displayName" class="field-error" role="alert">{{ profileErrors.displayName }}</p>
              </div>

              <div class="settings-field">
                <label for="account-bio">个人简介 <span>选填</span></label>
                <textarea
                  id="account-bio"
                  v-model="profileForm.bio"
                  class="settings-textarea"
                  rows="5"
                  maxlength="1200"
                  placeholder="介绍擅长的拍摄方向、合作方式或你想记录的故事"
                  :disabled="savingProfile"
                />
                <small>{{ profileForm.bio.length }}/1200，可使用换行组织内容。</small>
              </div>

              <div v-if="auth.isPhotographer" class="settings-field">
                <label for="account-residency">常驻地 <span>选填</span></label>
                <input
                  id="account-residency"
                  v-model="profileForm.location"
                  class="settings-input"
                  type="text"
                  maxlength="255"
                  placeholder="例如：中国-四川-成都"
                  :disabled="savingProfile"
                />
                <small>
                  可按「国家-省份-城市」层级填写，个人信息卡的地点标签只展示最详细的一级{{ residencyPreviewText }}。
                </small>
              </div>

              <label v-if="auth.isPhotographer" class="toggle-row" for="show-public-email">
                <span>
                  <strong>在摄影师主页公开邮箱</strong>
                  <small>{{ auth.user.email ? '仅展示已验证邮箱，可随时关闭。' : '绑定并验证邮箱后才能开启。' }}</small>
                </span>
                <input
                  id="show-public-email"
                  v-model="profileForm.showEmailOnProfile"
                  type="checkbox"
                  :disabled="savingProfile || !auth.user.email"
                />
              </label>
            </section>

            <div v-if="profileRequestError" class="request-error" role="alert">
              <CircleAlert :size="19" aria-hidden="true" />{{ profileRequestError }}
            </div>
            <div v-if="hasProfileChanges" class="unsaved-note" role="status">
              <RotateCcw :size="18" aria-hidden="true" />公开资料有尚未保存的修改。
            </div>
            <button
              type="submit"
              class="primary-button pressable"
              :disabled="savingProfile || Boolean(uploadingImage) || !hasProfileChanges"
            >
              <ion-spinner v-if="savingProfile" name="crescent" aria-hidden="true" />
              <Save v-else :size="18" aria-hidden="true" />
              {{ savingProfile ? '保存中…' : '保存公开资料' }}
            </button>
          </form>

          <div v-else class="security-workspace">
            <section class="settings-card">
              <header class="card-heading">
                <span><BadgeCheck :size="20" aria-hidden="true" /></span>
                <div>
                  <h2>登录标识与联系方式</h2>
                  <p>登录标识与已验证联系方式集中管理，方便在不同设备上安全登录。</p>
                </div>
              </header>

              <div class="readonly-list">
                <div>
                  <span><Hash :size="18" aria-hidden="true" /></span>
                  <p><small>用户 ID</small><strong>{{ auth.user.id }}</strong></p>
                  <em>不可修改</em>
                </div>
                <div>
                  <span><AtSign :size="18" aria-hidden="true" /></span>
                  <p><small>用户名 / 登录 ID</small><strong>@{{ auth.user.username || '尚未设置' }}</strong></p>
                  <em>注册后不可修改</em>
                </div>
              </div>

              <div class="contact-list">
                <div class="contact-row">
                  <span class="contact-icon"><Phone :size="19" aria-hidden="true" /></span>
                  <div>
                    <strong>手机号</strong>
                    <p>{{ contactValue('phone') }}</p>
                  </div>
                  <div class="contact-action">
                    <span class="status-badge" :class="contactStatus('phone').tone">{{ contactStatus('phone').label }}</span>
                    <button type="button" class="compact-button pressable" :disabled="sendingBindingCode || confirmingBinding || changingPassword || loggingOutAll" @click="openBinding('phone')">
                      {{ auth.user.phone ? '更换' : '绑定' }}
                    </button>
                  </div>
                </div>

                <div class="contact-row">
                  <span class="contact-icon"><Mail :size="19" aria-hidden="true" /></span>
                  <div>
                    <strong>邮箱</strong>
                    <p>{{ contactValue('email') }}</p>
                  </div>
                  <div class="contact-action">
                    <span class="status-badge" :class="contactStatus('email').tone">{{ contactStatus('email').label }}</span>
                    <button type="button" class="compact-button pressable" :disabled="sendingBindingCode || confirmingBinding || changingPassword || loggingOutAll" @click="openBinding('email')">
                      {{ auth.user.email ? '更换' : '绑定' }}
                    </button>
                  </div>
                </div>
              </div>
            </section>

            <section v-if="bindingChannel" class="settings-card binding-card" aria-labelledby="binding-title">
              <header class="binding-heading">
                <div>
                  <p>Verify contact</p>
                  <h2 id="binding-title">{{ bindingChannel === 'phone' ? '验证手机号' : '验证邮箱' }}</h2>
                </div>
                <button type="button" class="close-button pressable" aria-label="取消联系方式验证" :disabled="sendingBindingCode || confirmingBinding" @click="resetBinding">
                  <X :size="20" aria-hidden="true" />
                </button>
              </header>

              <div class="settings-field">
                <label for="binding-target">{{ bindingChannel === 'phone' ? '手机号' : '邮箱地址' }} <span>必填</span></label>
                <input
                  id="binding-target"
                  v-model="bindingTarget"
                  class="settings-input"
                  :type="bindingChannel === 'phone' ? 'tel' : 'email'"
                  :inputmode="bindingChannel === 'phone' ? 'tel' : 'email'"
                  :autocomplete="bindingChannel === 'phone' ? 'tel' : 'email'"
                  autocapitalize="none"
                  :disabled="Boolean(bindingChallengeId) || sendingBindingCode || confirmingBinding"
                  :aria-invalid="Boolean(bindingTargetError)"
                  @blur="validateBindingTarget"
                />
                <p v-if="bindingTargetError" class="field-error" role="alert">{{ bindingTargetError }}</p>
              </div>

              <template v-if="bindingChallengeId">
                <div class="verification-note" role="status">
                  <CheckCircle2 :size="19" aria-hidden="true" />
                  <p>验证码已发送至 <strong>{{ bindingMaskedTarget }}</strong>，约 {{ bindingExpiryMinutes }} 分钟内有效。</p>
                </div>
                <div class="settings-field">
                  <label for="binding-code">验证码 <span>必填</span></label>
                  <input
                    id="binding-code"
                    v-model="bindingCode"
                    class="settings-input code-input"
                    type="text"
                    inputmode="numeric"
                    autocomplete="one-time-code"
                    maxlength="10"
                    placeholder="请输入验证码"
                    :disabled="confirmingBinding"
                    :aria-invalid="Boolean(bindingCodeError)"
                    @blur="validateBindingCode"
                  />
                  <p v-if="bindingCodeError" class="field-error" role="alert">{{ bindingCodeError }}</p>
                </div>
              </template>

              <div v-if="bindingRequestError" class="request-error" role="alert">
                <CircleAlert :size="19" aria-hidden="true" />{{ bindingRequestError }}
              </div>

              <div class="binding-actions">
                <button
                  v-if="bindingChallengeId"
                  type="button"
                  class="secondary-button pressable"
                  :disabled="confirmingBinding"
                  @click="restartBinding"
                >
                  <RotateCcw :size="17" aria-hidden="true" />重新填写
                </button>
                <button
                  v-if="!bindingChallengeId"
                  type="button"
                  class="primary-button pressable"
                  :disabled="sendingBindingCode"
                  @click="requestBindingCode"
                >
                  <ion-spinner v-if="sendingBindingCode" name="crescent" aria-hidden="true" />
                  <Send v-else :size="18" aria-hidden="true" />
                  {{ sendingBindingCode ? '发送中…' : '获取验证码' }}
                </button>
                <button
                  v-else
                  type="button"
                  class="primary-button pressable"
                  :disabled="confirmingBinding"
                  @click="confirmBindingCode"
                >
                  <ion-spinner v-if="confirmingBinding" name="crescent" aria-hidden="true" />
                  <BadgeCheck v-else :size="18" aria-hidden="true" />
                  {{ confirmingBinding ? '验证中…' : '确认绑定' }}
                </button>
              </div>
            </section>

            <form class="settings-card password-card" novalidate @submit.prevent="submitPasswordChange">
              <header class="card-heading">
                <span><KeyRound :size="20" aria-hidden="true" /></span>
                <div>
                  <h2>修改登录密码</h2>
                  <p>修改成功后所有现有令牌都会失效，需要使用新密码重新登录。</p>
                </div>
              </header>

              <div class="settings-field">
                <label for="current-password">当前密码 <span>必填</span></label>
                <div class="password-field">
                  <input
                    id="current-password"
                    v-model="passwordForm.currentPassword"
                    class="settings-input"
                    :type="passwordVisibility.current ? 'text' : 'password'"
                    autocomplete="current-password"
                    :disabled="changingPassword"
                    :aria-invalid="Boolean(passwordErrors.currentPassword)"
                    @blur="validatePasswordField('currentPassword')"
                  />
                  <button type="button" class="password-toggle pressable" :aria-label="passwordVisibility.current ? '隐藏当前密码' : '显示当前密码'" @click="passwordVisibility.current = !passwordVisibility.current">
                    <EyeOff v-if="passwordVisibility.current" :size="19" aria-hidden="true" />
                    <Eye v-else :size="19" aria-hidden="true" />
                  </button>
                </div>
                <p v-if="passwordErrors.currentPassword" class="field-error" role="alert">{{ passwordErrors.currentPassword }}</p>
              </div>

              <div class="settings-field">
                <label for="new-password">新密码 <span>至少 8 个字符</span></label>
                <div class="password-field">
                  <input
                    id="new-password"
                    v-model="passwordForm.newPassword"
                    class="settings-input"
                    :type="passwordVisibility.next ? 'text' : 'password'"
                    autocomplete="new-password"
                    minlength="8"
                    maxlength="72"
                    :disabled="changingPassword"
                    :aria-invalid="Boolean(passwordErrors.newPassword)"
                    @blur="validatePasswordField('newPassword')"
                  />
                  <button type="button" class="password-toggle pressable" :aria-label="passwordVisibility.next ? '隐藏新密码' : '显示新密码'" @click="passwordVisibility.next = !passwordVisibility.next">
                    <EyeOff v-if="passwordVisibility.next" :size="19" aria-hidden="true" />
                    <Eye v-else :size="19" aria-hidden="true" />
                  </button>
                </div>
                <p v-if="passwordErrors.newPassword" class="field-error" role="alert">{{ passwordErrors.newPassword }}</p>
              </div>

              <div class="settings-field">
                <label for="confirm-password">确认新密码 <span>必填</span></label>
                <div class="password-field">
                  <input
                    id="confirm-password"
                    v-model="passwordForm.confirmPassword"
                    class="settings-input"
                    :type="passwordVisibility.confirm ? 'text' : 'password'"
                    autocomplete="new-password"
                    minlength="8"
                    maxlength="72"
                    :disabled="changingPassword"
                    :aria-invalid="Boolean(passwordErrors.confirmPassword)"
                    @blur="validatePasswordField('confirmPassword')"
                  />
                  <button type="button" class="password-toggle pressable" :aria-label="passwordVisibility.confirm ? '隐藏确认密码' : '显示确认密码'" @click="passwordVisibility.confirm = !passwordVisibility.confirm">
                    <EyeOff v-if="passwordVisibility.confirm" :size="19" aria-hidden="true" />
                    <Eye v-else :size="19" aria-hidden="true" />
                  </button>
                </div>
                <p v-if="passwordErrors.confirmPassword" class="field-error" role="alert">{{ passwordErrors.confirmPassword }}</p>
              </div>

              <div v-if="passwordRequestError" class="request-error" role="alert">
                <CircleAlert :size="19" aria-hidden="true" />{{ passwordRequestError }}
              </div>
              <button type="submit" class="primary-button pressable" :disabled="changingPassword || loggingOutAll">
                <ion-spinner v-if="changingPassword" name="crescent" aria-hidden="true" />
                <KeyRound v-else :size="18" aria-hidden="true" />
                {{ changingPassword ? '修改中…' : '修改密码并重新登录' }}
              </button>
            </form>

            <section class="settings-card danger-card">
              <header class="card-heading">
                <span><LogOut :size="20" aria-hidden="true" /></span>
                <div>
                  <h2>退出全部设备</h2>
                  <p>让当前手机、网页端和其他设备上的登录令牌同时失效。</p>
                </div>
              </header>
              <div v-if="dangerRequestError" class="request-error" role="alert">
                <CircleAlert :size="19" aria-hidden="true" />{{ dangerRequestError }}
              </div>
              <button type="button" class="danger-button pressable" :disabled="loggingOutAll || changingPassword" @click="confirmLogoutAll">
                <ion-spinner v-if="loggingOutAll" name="crescent" aria-hidden="true" />
                <LogOut v-else :size="18" aria-hidden="true" />
                {{ loggingOutAll ? '正在退出…' : '退出全部设备' }}
              </button>
            </section>
          </div>
        </template>
      </main>

      <ion-toast
        :is-open="Boolean(toastMessage)"
        :message="toastMessage"
        :duration="2800"
        position="bottom"
        @did-dismiss="toastMessage = ''"
      />
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { IonContent, IonPage, IonSpinner, IonToast, alertController } from '@ionic/vue'
import {
  AtSign,
  BadgeCheck,
  Camera,
  CheckCircle2,
  CircleAlert,
  Eye,
  EyeOff,
  Hash,
  ImagePlus,
  Images,
  KeyRound,
  LogOut,
  Mail,
  Phone,
  RotateCcw,
  Save,
  Send,
  ShieldCheck,
  UserRound,
  X,
} from 'lucide-vue-next'
import AvatarImage from '@/components/AvatarImage.vue'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import SegmentSwitch, { type SegmentItem } from '@/components/SegmentSwitch.vue'
import StatePanel from '@/components/StatePanel.vue'
import {
  changeCurrentPassword,
  confirmContactBinding,
  confirmVerificationCode,
  logoutAllDevices,
  requestContactBinding,
  updateCurrentUser,
  uploadCurrentUserAvatar,
  uploadCurrentUserBackground,
} from '@/api/auth'
import { getPhotographerSettings, savePhotographerResidency } from '@/api/availability'
import { getApiErrorMessage } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import type { AccountContactChannel, UserProfile } from '@/types/auth'
import {
  validateContactTarget,
  validateDisplayName,
  validatePasswordChange,
  validateProfileImage,
  validateVerificationCode,
  type PasswordChangeErrors,
} from '@/utils/account'
import { resolveMediaUrl } from '@/utils/media'
import { formatResidencyLabel } from '@/utils/photographerProfile'

type AccountSection = 'profile' | 'security'
type ImageKind = 'avatar' | 'background'
type PasswordField = keyof PasswordChangeErrors

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const activeSection = ref<AccountSection>(route.query.tab === 'security' ? 'security' : 'profile')
const sectionItems: SegmentItem[] = [
  { label: '个人资料', value: 'profile' },
  { label: '账号安全', value: 'security' },
]
const loading = ref(true)
const loadError = ref('')
const toastMessage = ref('')

const profileForm = reactive({
  displayName: '',
  bio: '',
  location: '',
  showEmailOnProfile: false,
})
const profileErrors = reactive({ displayName: '' })
const profileBaseline = ref('')
const savedResidency = ref('')
const savingProfile = ref(false)
const profileRequestError = ref('')

const avatarInput = ref<HTMLInputElement | null>(null)
const backgroundInput = ref<HTMLInputElement | null>(null)
const avatarPreviewUrl = ref('')
const backgroundPreviewUrl = ref('')
const uploadingImage = ref<ImageKind | ''>('')
const imageError = ref('')

const bindingChannel = ref<AccountContactChannel | null>(null)
const bindingTarget = ref('')
const bindingTargetError = ref('')
const bindingChallengeId = ref('')
const bindingMaskedTarget = ref('')
const bindingExpiresIn = ref(0)
const bindingCode = ref('')
const bindingCodeError = ref('')
const bindingRequestError = ref('')
const sendingBindingCode = ref(false)
const confirmingBinding = ref(false)

const passwordForm = reactive({ currentPassword: '', newPassword: '', confirmPassword: '' })
const passwordErrors = reactive<PasswordChangeErrors>({
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
})
const passwordVisibility = reactive({ current: false, next: false, confirm: false })
const passwordRequestError = ref('')
const changingPassword = ref(false)
const dangerRequestError = ref('')
const loggingOutAll = ref(false)

const avatarSource = computed(() => avatarPreviewUrl.value || auth.user?.avatar_url || '')
const coverSource = computed(() => backgroundPreviewUrl.value || resolveMediaUrl(auth.user?.background_url))
const residencyLabel = computed(() => formatResidencyLabel(profileForm.location))
const residencyPreviewText = computed(() => (residencyLabel.value ? `，当前会显示「${residencyLabel.value}」` : ''))
const bindingExpiryMinutes = computed(() => Math.max(1, Math.ceil(bindingExpiresIn.value / 60)))
const hasProfileChanges = computed(() => profileSnapshot() !== profileBaseline.value)
const hasSecurityDraft = computed(() => Boolean(
  bindingChannel.value
  || passwordForm.currentPassword
  || passwordForm.newPassword
  || passwordForm.confirmPassword,
))
const hasUnsavedChanges = computed(() => hasProfileChanges.value || hasSecurityDraft.value)

function profileSnapshot() {
  return JSON.stringify({
    displayName: profileForm.displayName.trim(),
    bio: profileForm.bio.trim(),
    location: profileForm.location.trim(),
    showEmailOnProfile: profileForm.showEmailOnProfile,
  })
}

function hydrateProfile(user: UserProfile) {
  profileForm.displayName = user.display_name || ''
  profileForm.bio = user.bio || ''
  profileForm.location = savedResidency.value
  profileForm.showEmailOnProfile = Boolean(user.show_email_on_profile && user.email)
  profileErrors.displayName = ''
  profileRequestError.value = ''
  profileBaseline.value = profileSnapshot()
}

async function loadResidency() {
  if (!auth.user || !auth.isPhotographer) {
    savedResidency.value = ''
    return
  }
  const profile = await getPhotographerSettings(auth.user.id).catch(() => null)
  savedResidency.value = profile?.location || ''
}

async function loadAccount() {
  loading.value = true
  loadError.value = ''
  try {
    await auth.initialize()
    if (!auth.user && auth.token) await auth.loadCurrentUser()
    if (!auth.user) {
      await router.replace({ name: 'login', query: { redirect: route.fullPath } })
      return
    }
    await loadResidency()
    hydrateProfile(auth.user)
  } catch (error) {
    loadError.value = getApiErrorMessage(error)
  } finally {
    loading.value = false
  }
}

function setSection(value: string) {
  activeSection.value = value === 'security' ? 'security' : 'profile'
  void router.replace({
    query: {
      ...route.query,
      tab: activeSection.value === 'security' ? 'security' : undefined,
    },
  })
}

function validateProfileName() {
  profileErrors.displayName = validateDisplayName(profileForm.displayName)
  return !profileErrors.displayName
}

async function saveProfile() {
  if (savingProfile.value || uploadingImage.value || !hasProfileChanges.value || !validateProfileName()) {
    if (profileErrors.displayName) document.getElementById('account-display-name')?.focus()
    return
  }

  savingProfile.value = true
  profileRequestError.value = ''
  try {
    const nextResidency = profileForm.location.trim()
    if (auth.isPhotographer && nextResidency !== savedResidency.value) {
      const profile = await savePhotographerResidency(nextResidency)
      savedResidency.value = profile.location || ''
    }
    const updated = await updateCurrentUser({
      display_name: profileForm.displayName.trim(),
      bio: profileForm.bio.trim(),
      show_email_on_profile: auth.isPhotographer ? profileForm.showEmailOnProfile : undefined,
    })
    auth.setUser(updated)
    hydrateProfile(updated)
    toastMessage.value = '个人资料已保存'
  } catch (error) {
    profileRequestError.value = getApiErrorMessage(error)
  } finally {
    savingProfile.value = false
  }
}

function openImagePicker(kind: ImageKind) {
  if (savingProfile.value || uploadingImage.value) return
  imageError.value = ''
  if (kind === 'avatar') avatarInput.value?.click()
  else backgroundInput.value?.click()
}

function revokePreview(kind: ImageKind) {
  const current = kind === 'avatar' ? avatarPreviewUrl.value : backgroundPreviewUrl.value
  if (current) URL.revokeObjectURL(current)
  if (kind === 'avatar') avatarPreviewUrl.value = ''
  else backgroundPreviewUrl.value = ''
}

async function handleImageSelection(event: Event, kind: ImageKind) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || uploadingImage.value || savingProfile.value) return

  const validationError = validateProfileImage(file)
  if (validationError) {
    imageError.value = validationError
    return
  }

  imageError.value = ''
  revokePreview(kind)
  const previewUrl = URL.createObjectURL(file)
  if (kind === 'avatar') avatarPreviewUrl.value = previewUrl
  else backgroundPreviewUrl.value = previewUrl
  uploadingImage.value = kind

  try {
    const updated = kind === 'avatar'
      ? await uploadCurrentUserAvatar(file)
      : await uploadCurrentUserBackground(file)
    auth.setUser(updated)
    toastMessage.value = kind === 'avatar' ? '头像已更新' : '主页封面已更新'
  } catch (error) {
    imageError.value = getApiErrorMessage(error)
  } finally {
    uploadingImage.value = ''
    revokePreview(kind)
  }
}

function contactValue(channel: AccountContactChannel) {
  if (!auth.user) return '未绑定'
  if (channel === 'phone') return auth.user.phone || '未绑定'
  return auth.user.email || auth.user.pending_email || '未绑定'
}

function contactStatus(channel: AccountContactChannel) {
  if (!auth.user) return { label: '未绑定', tone: 'neutral' }
  if (channel === 'phone') {
    if (auth.user.phone && auth.user.phone_verified) return { label: '已验证', tone: 'verified' }
    if (auth.user.phone) return { label: '待验证', tone: 'pending' }
    return { label: '未绑定', tone: 'neutral' }
  }
  if (auth.user.email && auth.user.email_verified) return { label: '已验证', tone: 'verified' }
  if (auth.user.pending_email) return { label: '待验证', tone: 'pending' }
  return { label: '未绑定', tone: 'neutral' }
}

async function openBinding(channel: AccountContactChannel) {
  bindingChannel.value = channel
  bindingTarget.value = channel === 'phone'
    ? (auth.user?.phone || '')
    : (auth.user?.email || auth.user?.pending_email || '')
  bindingTargetError.value = ''
  bindingChallengeId.value = ''
  bindingMaskedTarget.value = ''
  bindingExpiresIn.value = 0
  bindingCode.value = ''
  bindingCodeError.value = ''
  bindingRequestError.value = ''
  await nextTick()
  document.getElementById('binding-target')?.focus()
}

function resetBinding() {
  bindingChannel.value = null
  bindingTarget.value = ''
  bindingTargetError.value = ''
  bindingChallengeId.value = ''
  bindingMaskedTarget.value = ''
  bindingExpiresIn.value = 0
  bindingCode.value = ''
  bindingCodeError.value = ''
  bindingRequestError.value = ''
}

function restartBinding() {
  bindingChallengeId.value = ''
  bindingMaskedTarget.value = ''
  bindingExpiresIn.value = 0
  bindingCode.value = ''
  bindingCodeError.value = ''
  bindingRequestError.value = ''
  void nextTick(() => document.getElementById('binding-target')?.focus())
}

function validateBindingTarget() {
  bindingTargetError.value = bindingChannel.value
    ? validateContactTarget(bindingChannel.value, bindingTarget.value)
    : ''
  return !bindingTargetError.value
}

function validateBindingCode() {
  bindingCodeError.value = validateVerificationCode(bindingCode.value)
  return !bindingCodeError.value
}

async function requestBindingCode() {
  if (!bindingChannel.value || sendingBindingCode.value || !validateBindingTarget()) {
    if (bindingTargetError.value) document.getElementById('binding-target')?.focus()
    return
  }

  sendingBindingCode.value = true
  bindingRequestError.value = ''
  try {
    const challenge = await requestContactBinding(bindingChannel.value, bindingTarget.value.trim())
    bindingChallengeId.value = challenge.challenge_id
    bindingMaskedTarget.value = challenge.masked_target
    bindingExpiresIn.value = challenge.expires_in
    toastMessage.value = '验证码已发送'
    await nextTick()
    document.getElementById('binding-code')?.focus()
  } catch (error) {
    bindingRequestError.value = getApiErrorMessage(error)
  } finally {
    sendingBindingCode.value = false
  }
}

async function confirmBindingCode() {
  if (!bindingChannel.value || !bindingChallengeId.value || confirmingBinding.value || !validateBindingCode()) {
    if (bindingCodeError.value) document.getElementById('binding-code')?.focus()
    return
  }

  confirmingBinding.value = true
  bindingRequestError.value = ''
  try {
    const verification = await confirmVerificationCode(bindingChallengeId.value, bindingCode.value.trim())
    const updated = await confirmContactBinding(bindingChannel.value, verification.verification_token)
    const channelLabel = bindingChannel.value === 'phone' ? '手机号' : '邮箱'
    auth.setUser(updated)
    resetBinding()
    toastMessage.value = `${channelLabel}已验证并绑定`
  } catch (error) {
    bindingRequestError.value = getApiErrorMessage(error)
  } finally {
    confirmingBinding.value = false
  }
}

function validatePasswordField(field: PasswordField) {
  const errors = validatePasswordChange(passwordForm)
  passwordErrors[field] = errors[field]
  return !passwordErrors[field]
}

function validatePasswordForm() {
  Object.assign(passwordErrors, validatePasswordChange(passwordForm))
  const firstInvalid = (Object.keys(passwordErrors) as PasswordField[]).find((key) => passwordErrors[key])
  if (firstInvalid) {
    const targetId = {
      currentPassword: 'current-password',
      newPassword: 'new-password',
      confirmPassword: 'confirm-password',
    }[firstInvalid]
    document.getElementById(targetId)?.focus()
  }
  return !firstInvalid
}

function resetPasswordForm() {
  passwordForm.currentPassword = ''
  passwordForm.newPassword = ''
  passwordForm.confirmPassword = ''
  passwordErrors.currentPassword = ''
  passwordErrors.newPassword = ''
  passwordErrors.confirmPassword = ''
  passwordVisibility.current = false
  passwordVisibility.next = false
  passwordVisibility.confirm = false
  passwordRequestError.value = ''
}

async function confirmDiscardProfileChanges() {
  if (!hasProfileChanges.value) return true
  const alert = await alertController.create({
    header: '公开资料尚未保存',
    message: '继续修改密码会让当前会话失效，尚未保存的昵称或简介修改将丢失。',
    buttons: [
      { text: '返回保存', role: 'cancel' },
      { text: '放弃并继续', role: 'destructive' },
    ],
  })
  await alert.present()
  const result = await alert.onDidDismiss()
  return result.role === 'destructive'
}

async function submitPasswordChange() {
  if (changingPassword.value || loggingOutAll.value || !validatePasswordForm() || !await confirmDiscardProfileChanges()) return
  changingPassword.value = true
  passwordRequestError.value = ''
  try {
    await changeCurrentPassword({
      current_password: passwordForm.currentPassword,
      new_password: passwordForm.newPassword,
    })
    profileBaseline.value = profileSnapshot()
    resetBinding()
    resetPasswordForm()
    const alert = await alertController.create({
      header: '密码已修改',
      message: '为保护账号安全，所有设备都需要使用新密码重新登录。',
      buttons: ['重新登录'],
    })
    await alert.present()
    await alert.onDidDismiss()
    auth.clearSession()
    await router.replace({ name: 'login' })
  } catch (error) {
    passwordRequestError.value = getApiErrorMessage(error)
  } finally {
    changingPassword.value = false
  }
}

async function confirmLogoutAll() {
  if (loggingOutAll.value || changingPassword.value) return
  const alert = await alertController.create({
    header: '退出全部设备？',
    message: hasUnsavedChanges.value
      ? '所有登录令牌会立即失效，当前页面尚未提交的内容也会丢失。'
      : '当前手机、网页端和其他设备都需要重新登录。',
    buttons: [
      { text: '取消', role: 'cancel' },
      { text: '全部退出', role: 'destructive' },
    ],
  })
  await alert.present()
  const result = await alert.onDidDismiss()
  if (result.role !== 'destructive') return

  loggingOutAll.value = true
  dangerRequestError.value = ''
  try {
    await logoutAllDevices()
    profileBaseline.value = profileSnapshot()
    resetBinding()
    resetPasswordForm()
    auth.clearSession()
    await router.replace({ name: 'login' })
  } catch (error) {
    dangerRequestError.value = getApiErrorMessage(error)
  } finally {
    loggingOutAll.value = false
  }
}

async function confirmDiscardChanges() {
  if (!hasUnsavedChanges.value) return true
  const alert = await alertController.create({
    header: '放弃未提交内容？',
    message: '资料修改、联系方式验证或密码输入尚未完成，离开后需要重新填写。',
    buttons: [
      { text: '继续编辑', role: 'cancel' },
      { text: '放弃修改', role: 'destructive' },
    ],
  })
  await alert.present()
  const result = await alert.onDidDismiss()
  return result.role === 'destructive'
}

onBeforeRouteLeave(async () => confirmDiscardChanges())
onBeforeUnmount(() => {
  revokePreview('avatar')
  revokePreview('background')
})
onMounted(loadAccount)
</script>

<style scoped>
.account-content { --background: var(--paper); }

.account-shell {
  display: grid;
  gap: var(--space-5);
  width: min(100%, 720px);
  margin: 0 auto;
  padding: var(--space-4) var(--space-4) calc(var(--space-8) + env(safe-area-inset-bottom));
}

/* 顶部账号摘要：与其它页的提示块同一套浅底样式 */
.account-summary {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--brand-soft);
}

.account-summary p {
  margin: 0 0 2px;
  color: var(--brand);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: .12em;
  text-transform: uppercase;
}

.account-summary h1 { overflow: hidden; margin: 0; font-size: var(--text-lg); font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.account-summary small { display: block; overflow: hidden; margin-top: 4px; color: var(--ink-secondary); font-size: var(--text-xs); text-overflow: ellipsis; white-space: nowrap; }

.session-badge {
  display: inline-flex;
  min-height: 30px;
  align-items: center;
  gap: 5px;
  padding: 4px 9px;
  border-radius: var(--radius-pill);
  background: var(--surface-solid);
  color: var(--brand);
  font-size: var(--text-xs);
  font-weight: 700;
}

.account-form, .security-workspace { display: grid; gap: var(--space-5); }

/* 描边卡片，不用阴影（DESIGN.md §6） */
.settings-card {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface-solid);
}

.card-heading {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr);
  align-items: center;
  gap: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border);
}

.card-heading > span {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border-radius: var(--radius-md);
  background: var(--brand-soft);
  color: var(--brand);
}

.card-heading h2, .binding-heading h2 { margin: 0; font-size: var(--text-base); font-weight: 700; }
.card-heading p { margin: 3px 0 0; color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.55; }

.cover-editor { display: grid; gap: var(--space-3); }

.cover-preview {
  position: relative;
  overflow: hidden;
  aspect-ratio: 3 / 1;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-secondary);
}

.cover-preview img { width: 100%; height: 100%; object-fit: cover; }
.cover-empty { display: grid; height: 100%; place-items: center; align-content: center; gap: 6px; color: var(--ink-tertiary); font-size: var(--text-xs); }

/* 上传中压在预览图上的遮罩，用统一的图上遮罩色 */
.upload-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  background: var(--surface-overlay);
  color: var(--on-overlay);
  font-size: var(--text-sm);
  font-weight: 700;
}

.upload-overlay ion-spinner, .avatar-loading ion-spinner { width: 22px; height: 22px; }

.avatar-editor {
  display: grid;
  grid-template-columns: 76px minmax(0, 1fr);
  align-items: center;
  gap: var(--space-4);
  padding-top: var(--space-2);
  border-top: 1px solid var(--border);
}

.avatar-preview-wrap { position: relative; width: 76px; height: 76px; }

.avatar-loading {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--surface-overlay);
  color: var(--on-overlay);
}

.avatar-editor strong { font-size: var(--text-sm); font-weight: 700; }
.avatar-editor p { margin: 4px 0 var(--space-2); color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.5; }

.settings-field { display: grid; gap: 7px; }
.settings-field label { color: var(--ink); font-size: var(--text-sm); font-weight: 700; }
.settings-field label span { color: var(--ink-tertiary); font-size: var(--text-xs); font-weight: 400; }
.settings-field > small { color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.5; }

/* 灰底输入：边界靠填充表达，状态可识别靠强焦点环（DESIGN.md §3.5） */
.settings-input, .settings-textarea {
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

.settings-textarea { min-height: 128px; padding-block: var(--space-3); line-height: 1.65; resize: vertical; }
.settings-input:focus, .settings-textarea:focus { outline: 3px solid var(--focus-ring); outline-offset: 2px; }
.settings-input[aria-invalid="true"] { border-color: var(--danger); }
.settings-input:disabled, .settings-textarea:disabled { background: var(--surface-secondary); color: var(--ink-tertiary); opacity: .75; }

.toggle-row {
  display: flex;
  min-height: 62px;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border);
}

.toggle-row > span { display: grid; gap: 4px; }
.toggle-row strong { font-size: var(--text-sm); font-weight: 700; }
.toggle-row small { color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.45; }
.toggle-row input { width: 24px; height: 24px; flex: 0 0 auto; accent-color: var(--brand); }

.field-error { margin: 0; color: var(--danger); font-size: var(--text-xs); line-height: 1.5; }

.request-error, .unsaved-note {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  line-height: 1.55;
}

.request-error { border: 1px solid var(--danger); background: var(--danger-soft); color: var(--danger); }
/* 未保存提醒是待处理态，用琥珀而不是红色 */
.unsaved-note { border-left: 3px solid var(--warning); background: var(--warning-soft); color: var(--ink-secondary); }
.request-error svg, .unsaved-note svg { flex: 0 0 auto; margin-top: 1px; }

.primary-button, .secondary-button, .danger-button, .inline-action, .compact-button, .close-button {
  display: inline-flex;
  min-height: var(--touch-target);
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  border-radius: var(--radius-md);
  font-weight: 700;
}

.primary-button { width: 100%; padding: 0 var(--space-4); border: 0; background: var(--brand); color: var(--on-brand); }
.secondary-button { width: 100%; padding: 0 var(--space-4); border: 1px solid var(--brand); background: var(--surface-solid); color: var(--brand); }
.inline-action { padding: 0 var(--space-3); border: 0; background: var(--surface-secondary); color: var(--brand); font-size: var(--text-xs); }
.compact-button { min-width: 72px; padding: 0 var(--space-3); border: 0; background: var(--surface-secondary); color: var(--brand); font-size: var(--text-xs); }

.primary-button:disabled, .secondary-button:disabled, .danger-button:disabled,
.inline-action:disabled, .compact-button:disabled, .close-button:disabled {
  border-color: transparent;
  background: var(--surface-secondary);
  color: var(--ink-tertiary);
  opacity: .62;
}

.primary-button ion-spinner, .danger-button ion-spinner { width: 20px; height: 20px; }

/* 只读信息列表：描边容器 + 行分隔线 */
.readonly-list { overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface-solid); }
.readonly-list > div {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-2);
  min-height: 68px;
  padding: var(--space-3);
  border-bottom: 1px solid var(--border);
}
.readonly-list > div:last-child { border-bottom: 0; }
.readonly-list > div > span { display: grid; width: 34px; height: 34px; place-items: center; border-radius: var(--radius-pill); background: var(--brand-soft); color: var(--brand); }
.readonly-list p { display: grid; gap: 3px; min-width: 0; margin: 0; }
.readonly-list small { color: var(--ink-tertiary); font-size: var(--text-xs); }
.readonly-list strong { overflow: hidden; font-size: var(--text-sm); font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.readonly-list em { color: var(--ink-tertiary); font-size: var(--text-xs); font-style: normal; text-align: right; }

.contact-list { display: grid; gap: var(--space-2); }

.contact-row {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-3);
  min-height: 82px;
  padding: var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-solid);
}

.contact-icon { display: grid; width: 38px; height: 38px; place-items: center; border-radius: var(--radius-pill); background: var(--brand-soft); color: var(--brand); }
.contact-row strong { font-size: var(--text-sm); font-weight: 700; }
.contact-row p { overflow-wrap: anywhere; margin: 4px 0 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.45; }
.contact-action { display: grid; justify-items: end; gap: 6px; }

/* 状态徽章：已验证走成功色、待验证走警告色、其余中性（DESIGN.md §3.3） */
.status-badge { display: inline-flex; min-height: 24px; align-items: center; padding: 2px 8px; border-radius: var(--radius-pill); font-size: var(--text-xs); font-weight: 700; }
.status-badge.verified { background: var(--success-soft); color: var(--success); }
.status-badge.pending { background: var(--warning-soft); color: var(--warning); }
.status-badge.neutral { background: var(--surface-secondary); color: var(--ink-tertiary); }

.binding-card { border-left: 3px solid var(--brand); }

.binding-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border);
}

.binding-heading p { margin: 0 0 2px; color: var(--brand); font-size: var(--text-xs); font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }

.close-button { width: var(--touch-target); height: var(--touch-target); flex: 0 0 auto; border: 0; background: var(--surface-secondary); color: var(--ink-secondary); }

.verification-note {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--brand);
  background: var(--brand-soft);
  color: var(--brand);
}

.verification-note svg { flex: 0 0 auto; margin-top: 1px; }
.verification-note p { margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }
.verification-note strong { color: var(--ink); }

.code-input { font-variant-numeric: tabular-nums; letter-spacing: .18em; }

.binding-actions { display: grid; grid-template-columns: 1fr; gap: var(--space-3); }
.binding-actions:has(.secondary-button) { grid-template-columns: minmax(112px, .75fr) minmax(0, 1.25fr); }

.password-field { position: relative; }
.password-field .settings-input { padding-right: 58px; }

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

.danger-card { border-color: var(--danger); }
.danger-card .card-heading > span { background: var(--danger-soft); color: var(--danger); }
.danger-button { width: 100%; padding: 0 var(--space-4); border: 1px solid var(--danger); background: var(--surface-solid); color: var(--danger); }

@media (max-width: 420px) {
  .account-summary { grid-template-columns: 56px minmax(0, 1fr); }
  .account-summary :deep(.avatar) { width: 56px !important; height: 56px !important; }
  .session-badge { grid-column: 2; justify-self: start; }
  .readonly-list > div { grid-template-columns: 34px minmax(0, 1fr); }
  .readonly-list em { grid-column: 2; text-align: left; }
  .contact-row { grid-template-columns: 38px minmax(0, 1fr); }
  .contact-action { grid-column: 2; grid-template-columns: auto auto; align-items: center; justify-content: start; justify-items: start; }
}

@media (min-width: 640px) {
  .settings-card { padding: var(--space-5); }
  .cover-editor { grid-template-columns: minmax(0, 1fr) 190px; align-items: end; }
  .binding-actions { justify-self: end; width: min(100%, 420px); }
}
</style>