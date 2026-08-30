<template>
  <div class="dashboard">
    <h2>摄影师工作台</h2>

    <PhotographerStats />

    <el-tabs v-model="activeTab">
      <!-- 我的订单 -->
      <el-tab-pane label="我的订单" name="orders">
        <el-table :data="orders" v-loading="loadingOrders" stripe>
          <el-table-column prop="id" label="订单号" width="80" />
          <el-table-column prop="package_snapshot" label="方案" min-width="180" />
          <el-table-column label="预约日期" width="170">
            <template #default="{ row }">
              {{ new Date(row.appointment_time).toLocaleDateString('zh-CN') }}
            </template>
          </el-table-column>
          <el-table-column label="需求" min-width="150">
            <template #default="{ row }">
              {{ row.notes || '无' }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="240">
            <template #default="{ row }">
              <el-button
                v-if="row.active_reschedule_request"
                type="warning"
                size="small"
                @click="goOrderDetail(row)"
              >
                处理改期
              </el-button>
              <template v-else-if="row.status === 'pending'">
                <el-button type="success" size="small" @click="handleConfirm(row.id)">确认</el-button>
                <el-button type="danger" size="small" @click="handleReject(row.id)">拒绝</el-button>
              </template>
              <el-button
                v-else-if="row.status === 'confirmed'"
                type="primary"
                size="small"
                @click="handleStart(row.id)"
              >
                开始服务
              </el-button>
              <el-button
                v-else-if="row.status === 'in_progress'"
                type="primary"
                size="small"
                @click="openDeliveryDialog(row)"
              >
                交付作品
              </el-button>
              <span v-else>--</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 我的方案 -->
      <el-tab-pane label="我的方案" name="packages">
        <div style="margin-bottom:16px;">
          <el-button type="primary" @click="openPackageDialog(-1)">添加方案</el-button>
        </div>
        <el-table :data="packagesList" stripe>
          <el-table-column prop="name" label="方案名称" />
          <el-table-column label="价格" width="100">
            <template #default="{ row }">￥{{ row.price }}</template>
          </el-table-column>
          <el-table-column prop="duration" label="时间" width="90">
            <template #default="{ row }">{{ row.duration }}分钟</template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="140" />
          <el-table-column label="操作" width="150">
            <template #default="{ $index }">
              <el-button type="primary" size="small" @click="openPackageDialog($index)">编辑</el-button>
              <el-button type="danger" size="small" @click="removePackage($index)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!packagesList.length" description="暂无方案" />
      </el-tab-pane>

      <!-- 上传作品 -->
      <el-tab-pane label="上传作品" name="upload">
        <el-form label-width="80px">
          <el-form-item label="上传图片">
            <el-upload
              :auto-upload="false"
              :on-change="handleFileChange"
              :limit="1"
              accept="image/*"
            >
              <el-button type="primary">上传图片</el-button>
            </el-upload>
          </el-form-item>
          <el-form-item label="标题">
            <el-input v-model="workTitle" placeholder="如：春日写真系列" />
          </el-form-item>
          <el-form-item label="风格标签">
            <TagInput v-model="workTags" placeholder="输入风格后按回车添加，如：日系" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="workDesc" type="textarea" placeholder="作品描述" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="uploadWork" :loading="uploading" :disabled="!selectedFile">
              上传作品
            </el-button>
          </el-form-item>
        </el-form>

        <el-divider />
        <h4>我的作品集</h4>
        <div class="portfolio-grid">
          <div v-for="(work, idx) in portfolio" :key="idx" class="portfolio-item" @click="goWorkDetail(work)">
            <el-image :src="getUrl(work.url)" fit="cover" class="work-image" />
            <div class="work-info">
              <div class="work-title" v-if="work.title">{{ work.title }}</div>
              <div class="work-tags" v-if="getWorkTags(work).length">
                <el-tag v-for="tag in getWorkTags(work)" :key="tag" size="small">{{ tag }}</el-tag>
              </div>
              <span>{{ work.description }}</span>
            </div>
          </div>
          <el-empty v-if="!portfolio.length" description="暂无作品" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="showPackageDialog" :title="editingPackageIndex >= 0 ? '编辑方案' : '添加方案'" width="500px" @closed="resetPackageForm">
      <el-form :model="packageForm" label-width="100px">
        <el-form-item label="方案名称">
          <el-input v-model="packageForm.name" placeholder="如：个人写真" />
        </el-form-item>
        <el-form-item label="价格（元）">
          <el-input-number v-model="packageForm.price" :min="0" :step="100" style="width:100%" />
        </el-form-item>
        <el-form-item label="时长（分钟）">
          <el-input-number v-model="packageForm.duration" :min="30" :step="30" style="width:100%" />
        </el-form-item>
        <el-form-item label="风格领域">
          <TagInput v-model="packageStyleTags" placeholder="输入风格领域后按回车添加，如：复古" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="packageForm.description" type="textarea" :rows="2" placeholder="方案简介" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPackageDialog = false">取消</el-button>
        <el-button type="primary" @click="savePackage">确定</el-button>
      </template>
    </el-dialog>

    <!-- 交付作品弹窗 -->
    <el-dialog v-model="showDeliveryDialog" title="交付作品" width="500px" @closed="resetDeliveryForm">
      <el-form label-width="80px">
        <el-form-item label="上传作品">
          <el-upload
            v-model:file-list="deliveryFiles"
            :auto-upload="false"
            list-type="picture-card"
            accept="image/*"
            multiple
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
        </el-form-item>
        <el-form-item label="交付说明">
          <el-input
            v-model="deliveryDescription"
            type="textarea"
            :rows="3"
            placeholder="如：精修已完成，请查收"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDeliveryDialog = false">取消</el-button>
        <el-button type="primary" @click="submitDelivery" :loading="submittingDelivery">确认交付</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from 'lucide-vue-next'
import api from '../utils/api'
import { getMyPhotographerOrders, confirmOrder, rejectOrder, deliverWorks, startOrder } from '../api/order'
import PhotographerStats from '../components/PhotographerStats.vue'
import TagInput from '../components/TagInput.vue'
import { promptRejectReason } from '@/utils/orderRejectPrompt'

const router = useRouter()
const activeTab = ref('orders')

// ---- 订单 ----
const orders = ref([])
const loadingOrders = ref(false)

const fetchOrders = async () => {
  loadingOrders.value = true
  try {
    const res = await getMyPhotographerOrders()
    orders.value = res.data
  } finally {
    loadingOrders.value = false
  }
}

const handleConfirm = async (id) => {
  try {
    await ElMessageBox.confirm('确认接受？', '提示', { type: 'warning' })
    await confirmOrder(id)
    ElMessage.success('已确认')
    fetchOrders()
  } catch {}
}

const handleReject = async (id) => {
  try {
    const reason = await promptRejectReason()
    await rejectOrder(id, reason)
    ElMessage.info('已拒绝')
    fetchOrders()
  } catch {}
}

const statusType = (s) => ({ pending: 'warning', awaiting_customer_payment: 'warning', confirmed: 'success', reschedule_requested: 'warning', in_progress: 'success', delivered: '', received: '', reviewed: '', cancelled: 'info', completed: '' }[s] || '')
const statusLabel = (s) => ({ pending: '待确认', awaiting_customer_payment: '待客户支付', confirmed: '已确认', reschedule_requested: '改期待确认', in_progress: '拍摄中/待交付', delivered: '待客户验收', received: '已完成', reviewed: '已完成', cancelled: '已取消', completed: '已完成' }[s] || s)

const goOrderDetail = (order) => {
  if (order?.id) router.push(`/orders/${order.id}`)
}

// ---- 交付作品 ----
const showDeliveryDialog = ref(false)
const submittingDelivery = ref(false)
const deliveryFiles = ref([])
const deliveryDescription = ref('')
const currentDeliverOrder = ref(null)

const openDeliveryDialog = (order) => {
    currentDeliverOrder.value = order
    showDeliveryDialog.value = true
}

const resetDeliveryForm = () => {
    deliveryFiles.value = []
    deliveryDescription.value = ''
    currentDeliverOrder.value = null
}

const submitDelivery = async () => {
    if (!deliveryFiles.value.length) {
        ElMessage.warning('请至少上传一张作品')
        return
    }
    submittingDelivery.value = true
    try {
        const formData = new FormData()
        deliveryFiles.value.forEach(file => {
            formData.append('files', file.raw)
        })
        formData.append('description', deliveryDescription.value)
        await deliverWorks(currentDeliverOrder.value.id, formData)
        ElMessage.success('作品已交付')
        showDeliveryDialog.value = false
        fetchOrders()
    } catch {
    } finally {
        submittingDelivery.value = false
    }
}

// ---- 上传 ----
const selectedFile = ref(null)
const workTitle = ref('')
const workTags = ref([])
const workDesc = ref('')
const uploading = ref(false)
const portfolio = ref([])

const getUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return url
}

const getWorkTags = (work) => {
  if (Array.isArray(work?.tags)) return work.tags
  return (work?.tag || '')
    .split(/[,\uFF0C\u3001\n]/)
    .map((tag) => tag.trim())
    .filter(Boolean)
}

const fetchPortfolio = async () => {
  const res = await api.get('/users/me')
  const me = res.data
  try {
    const pRes = await api.get(`/photographers/profile/${me.id}`, { skipErrorHandler: true })
    portfolio.value = (pRes.data.portfolio || [])
  } catch {
    portfolio.value = []
  }
}

const handleFileChange = (file) => { selectedFile.value = file.raw }

const uploadWork = async () => {
  if (!selectedFile.value) return
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', selectedFile.value)
    fd.append('title', workTitle.value)
    fd.append('tag', workTags.value.join('、'))
    fd.append('description', workDesc.value)
    await api.post('/photographers/portfolio/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success('上传成功')
    workTitle.value = ''
    workTags.value = []
    workDesc.value = ''
    selectedFile.value = null
    fetchPortfolio()
    activeTab.value = 'upload'
  } finally {
    uploading.value = false
  }
}

// ---- 方案管理 ----
const showPackageDialog = ref(false)
const editingPackageIndex = ref(-1)
const packageForm = ref({ name: '', price: 699, duration: 120, description: '' })
const packageStyleTags = ref([])
const packagesList = ref([])

const fetchPackages = async () => {
  try {
    const res = await api.get('/users/me')
    const me = res.data
    try {
      const pRes = await api.get(`/photographers/profile/${me.id}`, { skipErrorHandler: true })
      packagesList.value = pRes.data.packages || []
    } catch {
      packagesList.value = []
    }
  } catch {}
}

const handleStart = async (id) => {
    try { await ElMessageBox.confirm('确认开始本次服务？', '开始服务', { type: 'warning' }) } catch { return }
    await startOrder(id)
    ElMessage.success('订单已进入履约中')
    fetchOrders()
}

const resetPackageForm = () => {
  packageForm.value = { name: '', price: 699, duration: 120, description: '' }
  packageStyleTags.value = []
  editingPackageIndex.value = -1
}

const openPackageDialog = (index) => {
  if (index >= 0) {
    const pkg = packagesList.value[index]
    packageForm.value = { name: pkg.name, price: pkg.price, duration: pkg.duration, description: pkg.description || '' }
    packageStyleTags.value = pkg.styles || pkg.includes || []
    editingPackageIndex.value = index
  } else {
    resetPackageForm()
  }
  showPackageDialog.value = true
}

const savePackage = () => {
  const pkg = {
    name: packageForm.value.name,
    price: packageForm.value.price,
    duration: packageForm.value.duration,
    description: packageForm.value.description,
    styles: packageStyleTags.value
  }
  if (editingPackageIndex.value >= 0) {
    packagesList.value[editingPackageIndex.value] = pkg
  } else {
    packagesList.value.push(pkg)
  }
  showPackageDialog.value = false
  uploadPackages()
}

const removePackage = async (index) => {
  try { await ElMessageBox.confirm('确定删除该方案？', '提示', { type: 'warning' }) } catch { return }
  packagesList.value.splice(index, 1)
  uploadPackages()
}

const goWorkDetail = (work) => {
  if (work && work.id) {
    router.push({ path: `/work/${work.id}`, state: { from: router.currentRoute.value.fullPath } })
  }
}

const uploadPackages = async () => {
  try {
    await api.post('/photographers/profile', { packages: packagesList.value })
    ElMessage.success('方案已保存')
  } catch {
    ElMessage.error('方案保存失败')
  }
}

onMounted(() => {
  fetchOrders()
  fetchPackages()
  fetchPortfolio()
})
</script>

<style scoped>
.dashboard {
    max-width: 1100px;
    margin: var(--space-8) auto;
    padding: 0 var(--space-6);
    color: var(--color-ink);
}
.dashboard h2 {
    color: var(--color-ink);
}
.portfolio-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-4);
}
.portfolio-item {
    background: var(--color-paper-light);
    border: var(--border-default);
    border-radius: var(--radius-md);
    overflow: hidden;
    cursor: pointer;
    transition: border-color 0.15s;
}
.portfolio-item:hover {
    border-color: var(--color-brand);
}
.work-image {
    width: 100%;
    height: 200px;
    display: block;
}
.work-info {
    padding: var(--space-2) 10px;
}
.work-title {
    font-size: calc(var(--text-sm) * 1rem);
    font-weight: 600;
    margin-bottom: var(--space-1);
    color: var(--color-ink);
}
.work-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 6px;
}
</style>
