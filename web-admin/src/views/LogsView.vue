<template>
  <h2 class="page-title">日志中心</h2>
  <el-tabs v-model="active" @tab-change="load">
    <el-tab-pane label="消息日志" name="messages" />
    <el-tab-pane label="错误日志" name="errors" />
    <el-tab-pane label="LLM 调用" name="llm" />
  </el-tabs>

  <el-table v-if="active !== 'llm'" :data="logs" border>
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column prop="group_id" label="群号" />
    <el-table-column prop="user_id" label="用户" />
    <el-table-column prop="content" label="内容" />
    <el-table-column prop="status" label="状态" />
    <el-table-column prop="drop_reason" label="原因" />
    <el-table-column prop="created_at" label="时间" />
  </el-table>

  <el-table v-else :data="logs" border>
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column prop="group_id" label="群号" />
    <el-table-column prop="user_id" label="用户" />
    <el-table-column prop="skill_name" label="Skill" />
    <el-table-column prop="model" label="模型" />
    <el-table-column prop="status" label="状态" />
    <el-table-column prop="prompt_tokens" label="输入" />
    <el-table-column prop="completion_tokens" label="输出" />
    <el-table-column prop="latency_ms" label="耗时(ms)" />
    <el-table-column prop="created_at" label="时间" />
  </el-table>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const logs = ref<any[]>([])
const active = ref('messages')

async function load() {
  const url = active.value === 'errors' ? '/system/errors' : active.value === 'llm' ? '/usage/llm' : '/system/logs'
  const { data } = await api.get(url)
  logs.value = data
}

onMounted(load)
</script>
