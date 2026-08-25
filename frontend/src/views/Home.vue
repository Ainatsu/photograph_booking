<template>
  <div class="home">
    <section class="hero">
      <h1 class="hero-title">好拍档</h1>
      <p class="hero-subtitle">发现风格契合的摄影师，轻松预约拍摄</p>
      <div class="hero-actions">
        <router-link to="/discover" class="btn btn-primary">浏览艺术家</router-link>
        <router-link to="/works" class="btn btn-secondary">探索作品</router-link>
      </div>
    </section>

    <section class="quick-links">
      <router-link to="/packages" class="quick-link">
        <div class="quick-link-icon">
          <el-icon :size="24"><Collection /></el-icon>
        </div>
        <span class="quick-link-label">拍摄方案</span>
        <span class="quick-link-desc">查看摄影师提供的拍摄套餐</span>
      </router-link>
      <router-link to="/projects" class="quick-link">
        <div class="quick-link-icon">
          <el-icon :size="24"><Notebook /></el-icon>
        </div>
        <span class="quick-link-label">创作企划</span>
        <span class="quick-link-desc">发现或发起摄影项目</span>
      </router-link>
      <router-link v-if="token" to="/my-orders" class="quick-link">
        <div class="quick-link-icon">
          <el-icon :size="24"><List /></el-icon>
        </div>
        <span class="quick-link-label">我的订单</span>
        <span class="quick-link-desc">查看预约和订单状态</span>
      </router-link>
    </section>

    <section class="bg-section">
      <div class="bg-label">页面背景设置</div>
      <div class="bg-customizer">
        <input
          ref="fileInputRef"
          type="file"
          accept="image/*"
          style="display: none"
          @change="onFileChange"
        />
        <button class="btn btn-secondary btn-sm" @click="fileInputRef?.click()">
          <el-icon :size="16" style="margin-right:4px"><Picture /></el-icon>
          选择背景图片
        </button>
        <button v-if="hasCustomBg" class="btn btn-text btn-sm" @click="removeBg">
          恢复默认
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ClipboardList as List, Image as Picture, Images as Collection, NotebookTabs as Notebook } from 'lucide-vue-next'

const fileInputRef = ref(null)
const token = ref(localStorage.getItem('token'))

const hasCustomBg = computed(() => !!localStorage.getItem('custom_bg'))

const onFileChange = (e) => {
  const file = e.target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    localStorage.setItem('custom_bg', reader.result)
    window.dispatchEvent(new Event('custom-bg-change'))
    e.target.value = ''
  }
  reader.readAsDataURL(file)
}

const removeBg = () => {
  localStorage.removeItem('custom_bg')
  window.dispatchEvent(new Event('custom-bg-change'))
}
</script>

<style scoped>
.home {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--space-16) var(--space-4) var(--space-8);
}

/* --- Hero --- */
.hero {
  text-align: center;
  padding: var(--space-16) 0 var(--space-12);
  border-bottom: var(--border-light);
  margin-bottom: var(--space-12);
}

.hero-title {
  font-size: var(--text-4xl);
  font-weight: 700;
  color: var(--color-ink);
  margin: 0 0 var(--space-4);
  letter-spacing: 0.02em;
  line-height: var(--leading-normal);
}

.hero-subtitle {
  font-size: var(--text-lg);
  color: var(--color-ink-secondary);
  margin: 0 0 var(--space-8);
  line-height: var(--leading-relaxed);
}

.hero-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: center;
  flex-wrap: wrap;
}

/* 首页按钮变体 */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-sans);
  font-size: var(--text-base);
  font-weight: 500;
  border: var(--border-default);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background-color 150ms ease, color 150ms ease, border-color 150ms ease;
  text-decoration: none;
  min-height: 44px;
  padding: 0 var(--space-6);
  white-space: nowrap;
}

.btn-primary {
  background: var(--color-brand);
  color: #fff;
  border-color: var(--color-brand);
}

.btn-primary:hover {
  background: var(--color-brand-hover);
  border-color: var(--color-brand-hover);
}

.btn-primary:active {
  background: var(--color-brand-active);
  border-color: var(--color-brand-active);
}

.btn-secondary {
  background: transparent;
  color: var(--color-ink);
  border-color: var(--color-border);
}

.btn-secondary:hover {
  border-color: var(--color-ink);
  background: var(--color-brand-light);
}

.btn-text {
  background: transparent;
  color: var(--color-ink-secondary);
  border: none;
}

.btn-text:hover {
  color: var(--color-danger);
}

.btn-sm {
  font-size: var(--text-sm);
  min-height: 36px;
  padding: 0 var(--space-4);
}

/* --- 快捷入口 --- */
.quick-links {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-12);
}

.quick-link {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: var(--space-6) var(--space-4);
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
  text-decoration: none;
  color: var(--color-ink);
  transition: border-color 150ms ease, background-color 150ms ease;
}

.quick-link:hover {
  border-color: var(--color-brand);
  background: var(--color-brand-light);
}

.quick-link-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: var(--radius-full);
  background: var(--color-brand-light);
  color: var(--color-brand);
  margin-bottom: var(--space-3);
  transition: background-color 150ms ease;
}

.quick-link:hover .quick-link-icon {
  background: var(--color-brand);
  color: #fff;
}

.quick-link-label {
  font-size: var(--text-base);
  font-weight: 600;
  margin-bottom: var(--space-1);
  color: var(--color-ink);
}

.quick-link-desc {
  font-size: var(--text-sm);
  color: var(--color-ink-tertiary);
  line-height: var(--leading-normal);
}

/* --- 背景设置 --- */
.bg-section {
  padding-top: var(--space-8);
  border-top: var(--border-light);
}

.bg-label {
  font-size: var(--text-sm);
  color: var(--color-ink-tertiary);
  margin-bottom: var(--space-3);
}

.bg-customizer {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

/* --- 响应式 --- */
@media (max-width: 768px) {
  .home {
    padding: var(--space-8) var(--space-4) var(--space-6);
  }

  .hero {
    padding: var(--space-10) 0 var(--space-8);
    margin-bottom: var(--space-8);
  }

  .hero-title {
    font-size: var(--text-3xl);
  }

  .hero-subtitle {
    font-size: var(--text-base);
  }

  .quick-links {
    grid-template-columns: 1fr;
    gap: var(--space-3);
  }

  .quick-link {
    flex-direction: row;
    text-align: left;
    padding: var(--space-4);
    gap: var(--space-3);
  }

  .quick-link-icon {
    width: 40px;
    height: 40px;
    margin-bottom: 0;
    flex-shrink: 0;
  }

  .quick-link-label {
    margin-bottom: 0;
  }

  .quick-link-desc {
    display: none;
  }
}

@media (min-width: 768px) {
  .home {
    padding: var(--space-16) var(--space-8) var(--space-8);
  }
}
</style>
