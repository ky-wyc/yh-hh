<template>
  <h2 class="page-title">日志中心</h2>
  <el-tabs v-model="active" @tab-change="load">
    <el-tab-pane label="消息日志" name="messages" />
    <el-tab-pane label="错误日志" name="errors" />
    <el-tab-pane label="LLM 调用" name="llm" />
    <el-tab-pane label="审计日志" name="audit" />
  </el-tabs>

  <el-card v-if="active === 'audit'" class="filter-card">
    <el-form :inline="true" :model="auditFilters">
      <el-form-item label="群号">
        <el-input v-model="auditFilters.group_id" clearable placeholder="留空全部" />
      </el-form-item>
      <el-form-item label="操作">
        <el-input v-model="auditFilters.action" clearable placeholder="如 warn / flood_mute" />
      </el-form-item>
      <el-form-item label="目标类型">
        <el-input v-model="auditFilters.target_type" clearable placeholder="如 user" />
      </el-form-item>
      <el-form-item label="目标">
        <el-input v-model="auditFilters.target_id" clearable placeholder="用户 QQ 或目标 ID" />
      </el-form-item>
      <el-form-item label="条数">
        <el-input-number v-model="auditFilters.limit" :min="1" :max="200" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="load">查询</el-button>
        <el-button @click="resetAuditFilters">重置</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-table v-if="active === 'messages' || active === 'errors'" :data="logs" border>
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column prop="message_id" label="消息ID" width="110" />
    <el-table-column prop="group_id" label="群号" />
    <el-table-column prop="user_id" label="用户" />
    <el-table-column prop="content" label="内容" />
    <el-table-column prop="status" label="状态" />
    <el-table-column prop="drop_reason" label="原因" />
    <el-table-column prop="created_at" label="时间" />
  </el-table>

  <el-table v-else-if="active === 'llm'" :data="logs" border>
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

  <el-table v-else :data="logs" border>
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column prop="actor_user_id" label="操作者" />
    <el-table-column prop="actor_role" label="角色" />
    <el-table-column prop="group_id" label="群号" />
    <el-table-column prop="action" label="操作" />
    <el-table-column prop="target_type" label="目标类型" />
    <el-table-column prop="target_id" label="目标" />
    <el-table-column prop="detail_json" label="详情" min-width="220" show-overflow-tooltip />
    <el-table-column prop="result" label="结果" />
    <el-table-column prop="created_at" label="时间" />
  </el-table>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const logs = ref<any[]>([])
const active = ref('messages')
const loading = ref(false)
const auditFilters = reactive({
  group_id: '',
  action: '',
  target_type: '',
  target_id: '',
  limit: 50
})

function validateAuditFilters() {
  if (auditFilters.group_id.trim() && !/^\d+$/.test(auditFilters.group_id.trim())) {
    ElMessage.warning('群号只能填写数字，或留空')
    return false
  }
  return true
}

async function load() {
  if (active.value === 'audit' && !validateAuditFilters()) return
  const url =
    active.value === 'errors'
      ? '/system/errors'
      : active.value === 'llm'
        ? '/usage/llm'
        : active.value === 'audit'
          ? '/audit-logs'
          : '/system/logs'
  const params =
    active.value === 'audit'
      ? {
          group_id: auditFilters.group_id.trim() || undefined,
          action: auditFilters.action.trim() || undefined,
          target_type: auditFilters.target_type.trim() || undefined,
          target_id: auditFilters.target_id.trim() || undefined,
          limit: auditFilters.limit
        }
      : undefined
  loading.value = true
  try {
    const { data } = await api.get(url, { params })
    logs.value = data
  } finally {
    loading.value = false
  }
}

function resetAuditFilters() {
  auditFilters.group_id = ''
  auditFilters.action = ''
  auditFilters.target_type = ''
  auditFilters.target_id = ''
  auditFilters.limit = 50
  load()
}

onMounted(load)
</script>

<style scoped>
.filter-card {
  margin-bottom: 16px;
}
</style>
