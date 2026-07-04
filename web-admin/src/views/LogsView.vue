<template>
  <h2 class="page-title">日志中心</h2>
  <el-table :data="logs" border>
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column prop="group_id" label="群号" />
    <el-table-column prop="user_id" label="用户" />
    <el-table-column prop="content" label="内容" />
    <el-table-column prop="status" label="状态" />
    <el-table-column prop="drop_reason" label="原因" />
    <el-table-column prop="created_at" label="时间" />
  </el-table>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const logs = ref<any[]>([])

onMounted(async () => {
  const { data } = await api.get('/system/logs')
  logs.value = data
})
</script>

