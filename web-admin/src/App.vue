<template>
  <router-view v-if="$route.path === '/login'" />
  <el-container v-else class="layout">
    <el-aside width="236px" class="sidebar">
      <div class="brand">QQBot Admin</div>
      <el-menu router :default-active="$route.path" background-color="#0f172a" text-color="#cbd5e1" active-text-color="#fff">
        <el-menu-item index="/">仪表盘</el-menu-item>
        <el-menu-item index="/groups">群管理</el-menu-item>
        <el-menu-item index="/keywords">关键词规则</el-menu-item>
        <el-menu-item index="/knowledge">知识库</el-menu-item>
        <el-menu-item index="/memories">长期记忆</el-menu-item>
        <el-menu-item index="/tasks">定时任务</el-menu-item>
        <el-menu-item index="/llm">系统设置</el-menu-item>
        <el-menu-item index="/logs">日志中心</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="topbar">
        <span>新一代 QQ 群机器人 MVP</span>
        <el-button size="small" @click="logout">退出</el-button>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { clearToken } from './auth'

const router = useRouter()

function logout() {
  clearToken()
  router.push('/login')
}
</script>
