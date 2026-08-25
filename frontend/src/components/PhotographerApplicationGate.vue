<template>
  <section class="application-gate">
    <div class="gate-head">
      <div>
        <h3>申请成为摄影师</h3>
        <p>提交基础资料和代表作品，审核通过后即可使用摄影师订单、应邀、方案和数据功能。</p>
      </div>
      <el-tag :type="statusType">{{ statusLabel }}</el-tag>
    </div>

    <el-alert
      v-if="application?.status === 'pending'"
      title="申请已提交，等待管理员审核"
      type="warning"
      show-icon
      :closable="false"
      class="gate-alert"
    />
    <el-alert
      v-if="application?.status === 'rejected'"
      :title="application.review_note || '申请未通过，请完善资料后重新提交'"
      type="error"
      show-icon
      :closable="false"
      class="gate-alert"
    />

    <el-form :model="form" label-width="110px" class="application-form" v-loading="loading">
      <el-form-item label="基础信息" required>
        <el-input
          v-model="form.profile_intro"
          type="textarea"
          :rows="3"
          placeholder="介绍你的拍摄经验、擅长题材或服务方式"
        />
      </el-form-item>
      <el-form-item label="地区" required>
        <RegionSelector v-model="form.location" />
      </el-form-item>
      <el-form-item label="设备信息" required>
        <el-input v-model="form.equipment" placeholder="如：Sony A7M4 + 24-70mm F2.8" />
      </el-form-item>
      <el-form-item label="风格领域" required>
        <TagInput v-model="form.styles" placeholder="输入风格领域后按回车添加，如：人像" />
      </el-form-item>
      <el-form-item label="提交作品" required>
        <div class="works-field">
          <el-upload
            v-model:file-list="workFiles"
            :auto-upload="false"
            list-type="picture-card"
            accept="image/*"
            multiple
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
          <div v-if="submittedWorks.length" class="submitted-works">
            <div v-for="work in submittedWorks" :key="work.id || work.url" class="submitted-work">
              <el-image :src="getFullUrl(work.thumbnail_url || work.url)" fit="cover" />
              <span>{{ work.title || '已提交作品' }}</span>
            </div>
          </div>
        </div>
      </el-form-item>
      <div class="form-actions">
        <el-button type="primary" @click="submitApplication" :loading="submitting">
          {{ application ? '更新申请' : '提交申请' }}
        </el-button>
      </div>
    </el-form>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from 'lucide-vue-next'
import { getMyPhotographerApplication, submitPhotographerApplication } from '@/api/photographerApplication'
import api from '@/utils/api'
import TagInput from './TagInput.vue'
import RegionSelector from './RegionSelector.vue'

const emit = defineEmits(['submitted'])

const loading = ref(false)
const submitting = ref(false)
const application = ref(null)
const workFiles = ref([])
const submittedWorks = ref([])

const form = reactive({
  profile_intro: '',
  location: '',
  equipment: '',
  styles: [],
})

const statusLabel = computed(() => {
  if (!application.value) return '未提交'
  return {
    pending: '审核中',
    approved: '已通过',
    rejected: '未通过',
  }[application.value.status] || application.value.status
})

const statusType = computed(() => {
  if (!application.value) return 'info'
  return {
    pending: 'warning',
    approved: 'success',
    rejected: 'danger',
  }[application.value.status] || 'info'
})

const getFullUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return url
}

const hydrateFromApplication = (data) => {
  application.value = data
  if (!data) return
  form.profile_intro = data.profile_intro || ''
  form.location = data.location || ''
  form.equipment = data.equipment || ''
  form.styles = data.styles || []
  submittedWorks.value = data.portfolio_refs || []
}

const fetchApplication = async () => {
  loading.value = true
  try {
    const res = await getMyPhotographerApplication()
    hydrateFromApplication(res.data)
  } catch {
    hydrateFromApplication(null)
  } finally {
    loading.value = false
  }
}

const validateForm = () => {
  if (!form.profile_intro.trim()) return '请填写基础摄影师信息'
  if (!form.location.trim()) return '请选择地区'
  if (!form.equipment.trim()) return '请填写设备信息'
  if (!form.styles.length) return '请至少填写一个风格领域'
  if (!submittedWorks.value.length && !workFiles.value.length) return '请至少提交一个作品'
  return ''
}

const uploadPendingWorks = async () => {
  const uploaded = []
  const files = workFiles.value.filter((file) => file.raw)
  for (const file of files) {
    const fd = new FormData()
    fd.append('file', file.raw)
    fd.append('title', file.name || '申请作品')
    fd.append('description', form.profile_intro)
    fd.append('tag', form.styles.join(','))
    const res = await api.post('/photographers/portfolio/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    uploaded.push(res.data.work)
  }
  workFiles.value = []
  return uploaded
}

const submitApplication = async () => {
  const message = validateForm()
  if (message) {
    ElMessage.warning(message)
    return
  }

  submitting.value = true
  try {
    const uploadedWorks = await uploadPendingWorks()
    const portfolioRefs = [...submittedWorks.value, ...uploadedWorks]
    const res = await submitPhotographerApplication({
      profile_intro: form.profile_intro,
      location: form.location,
      equipment: form.equipment,
      styles: form.styles,
      portfolio_refs: portfolioRefs,
    })
    hydrateFromApplication(res.data)
    ElMessage.success('申请已提交，等待管理员审核')
    emit('submitted', res.data)
  } finally {
    submitting.value = false
  }
}

onMounted(fetchApplication)
</script>

<style scoped>
.application-gate {
  padding: 20px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}
.gate-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.gate-head h3 {
  margin: 0 0 6px;
  font-size: 18px;
  color: #1f2937;
}
.gate-head p {
  margin: 0;
  color: #606266;
  line-height: 1.6;
}
.gate-alert {
  margin-bottom: 16px;
}
.application-form {
  max-width: 760px;
}
.works-field {
  width: 100%;
}
.submitted-works {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
  margin-top: 12px;
}
.submitted-work {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  background: #fafafa;
}
.submitted-work .el-image {
  width: 100%;
  aspect-ratio: 1 / 1;
  display: block;
}
.submitted-work span {
  display: block;
  padding: 6px 8px;
  font-size: 12px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
