<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2>管理后台登录</h2>
      <el-form :model="form" label-width="60px">
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="管理员邮箱" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="管理员密码" @keyup.enter="login" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="login" :loading="loading" style="width:100%">登录</el-button>
        </el-form-item>
      </el-form>
      <p class="tip">默认: admin@photobook.com / admin123</p>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../utils/api'

const router = useRouter()
const form = ref({ email: 'admin@photobook.com', password: 'admin123' })
const loading = ref(false)

const login = async () => {
  loading.value = true
  try {
    const res = await api.post('/login', {
      email: form.value.email,
      password: form.value.password,
    })
    localStorage.setItem('admin_token', res.data.access_token)
    router.push('/dashboard')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: #FAF7F2;
}

.login-card {
  width: 400px;
  max-width: calc(100vw - 32px);
  background: #FFFDF9;
  border: 1px solid #D9D3CB;
  border-radius: 4px;
  box-shadow: none;
}

.login-card :deep(.el-card__body) {
  padding: 32px;
}

h2 {
  text-align: center;
  margin-bottom: 24px;
  color: #1A1A1A;
  font-size: 1.25rem;
  font-weight: 700;
}

.tip {
  text-align: center;
  color: #9C9892;
  font-size: 0.75rem;
  margin-top: 16px;
}

:deep(.el-form-item__label) {
  color: #6B6560;
}

:deep(.el-input__wrapper) {
  background: #FAF7F2;
  border: 1px solid #D9D3CB;
  border-radius: 4px;
  box-shadow: none;
}

:deep(.el-input__wrapper:hover) {
  border-color: #6B6560;
}

:deep(.el-input__wrapper.is-focus) {
  border-color: #2D5A27;
  box-shadow: none;
}

:deep(.el-button--primary) {
  background: #2D5A27;
  border-color: #2D5A27;
  color: #FFFDF9;
}

:deep(.el-button--primary:hover) {
  background: #3A6E33;
  border-color: #3A6E33;
}

:deep(.el-button--primary:active) {
  background: #1F3F1A;
  border-color: #1F3F1A;
}
</style>
