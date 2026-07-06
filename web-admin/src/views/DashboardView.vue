<template>
  <h2 class="page-title">仪表盘</h2>
  <el-row :gutter="16">
    <el-col :span="6" v-for="item in cards" :key="item.label">
      <el-card>
        <div class="metric-label">{{ item.label }}</div>
        <div class="metric-value">{{ item.value }}</div>
      </el-card>
    </el-col>
  </el-row>

  <el-row :gutter="16" class="section-row">
    <el-col :span="12">
      <el-card>
        <template #header>运行状态</template>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="API">{{ ready.status ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="数据库">{{ ready.database ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="缓存">{{ cacheStatus }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-col>
    <el-col :span="12">
      <el-card>
        <template #header>OneBot 状态</template>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="连接">
            <el-tag :type="onebot.online ? 'success' : 'danger'">
              {{ onebot.online ? '在线' : '离线' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="活动">{{ activityText }}</el-descriptions-item>
          <el-descriptions-item label="模式">{{ onebot.connection_mode ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="连接时间">{{ onebot.connected_at ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="在线时长">{{ formatDuration(onebot.connected_seconds) }}</el-descriptions-item>
          <el-descriptions-item label="断开时间">{{ onebot.disconnected_at ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="离线时长">{{ formatDuration(onebot.offline_seconds) }}</el-descriptions-item>
          <el-descriptions-item label="最近事件">{{ onebot.last_event_at ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="事件距今">{{ formatDuration(onebot.last_event_age_seconds) }}</el-descriptions-item>
          <el-descriptions-item label="最近动作">{{ onebot.last_action_at ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="动作距今">{{ formatDuration(onebot.last_action_age_seconds) }}</el-descriptions-item>
          <el-descriptions-item label="最近错误">{{ onebot.last_error || '-' }}</el-descriptions-item>
          <el-descriptions-item label="恢复提示">{{ onebot.recovery_hint || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const overview = ref<Record<string, unknown>>({})
const ready = ref<Record<string, any>>({})
const onebot = ref<Record<string, any>>({})
const cards = computed(() => [
  { label: '消息数', value: overview.value.messages ?? '-' },
  { label: '回复数', value: overview.value.replies ?? '-' },
  { label: '启用群', value: overview.value.enabled_groups ?? '-' },
  { label: 'OneBot', value: overview.value.onebot_online ? '在线' : '离线' }
])
const cacheStatus = computed(() => {
  const cache = ready.value.cache
  if (!cache) return '-'
  if (typeof cache === 'string') return cache
  return `${cache.backend ?? '-'} / ${cache.status ?? '-'}`
})
const activityText = computed(() => {
  const labels: Record<string, string> = {
    active: '有收发记录',
    waiting_for_event: '等待入站事件',
    waiting_for_action: '等待出站动作',
    offline: '离线'
  }
  const state = String(onebot.value.activity_state || '')
  return labels[state] || state || '-'
})

function formatDuration(value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  const seconds = Number(value)
  if (!Number.isFinite(seconds)) return '-'
  if (seconds < 60) return `${Math.max(0, Math.floor(seconds))} 秒`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} 分 ${Math.floor(seconds % 60)} 秒`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时 ${minutes % 60} 分`
  const days = Math.floor(hours / 24)
  return `${days} 天 ${hours % 24} 小时`
}

onMounted(async () => {
  const [{ data: overviewData }, { data: readyData }, { data: onebotData }] = await Promise.all([
    api.get('/dashboard/overview'),
    api.get('/system/ready'),
    api.get('/system/onebot-status')
  ])
  overview.value = overviewData
  ready.value = readyData
  onebot.value = onebotData
})
</script>

<style scoped>
.section-row {
  margin-top: 16px;
}

.metric-label {
  color: #64748b;
}
.metric-value {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 700;
}
</style>
