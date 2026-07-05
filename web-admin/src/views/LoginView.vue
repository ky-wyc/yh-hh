<template>
  <div class="login-page">
    <el-card class="login-card">
      <h1>QQBot Admin</h1>
      <el-form @submit.prevent="submit">
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" placeholder="密码" show-password />
        </el-form-item>
        <el-button type="primary" class="login-btn" @click="submit">登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { setToken } from '../auth'

const router = useRouter()
const username = ref('admin')
const password = ref('')

async function submit() {
  try {
    const { data } = await api.post('/auth/login', { username: username.value, password: password.value })
    setToken(data.access_token)
    router.push('/')
  } catch {
    ElMessage.error('登录失败')
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: #eef2f7;
}

.login-card {
  width: 360px;
}

.login-btn {
  width: 100%;
}
</style>
