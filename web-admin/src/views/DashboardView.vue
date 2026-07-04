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
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const overview = ref<Record<string, unknown>>({})
const cards = computed(() => [
  { label: '消息数', value: overview.value.messages ?? '-' },
  { label: '回复数', value: overview.value.replies ?? '-' },
  { label: '启用群', value: overview.value.enabled_groups ?? '-' },
  { label: 'OneBot', value: overview.value.onebot_online ? '在线' : '离线' }
])

onMounted(async () => {
  const { data } = await api.get('/dashboard/overview')
  overview.value = data
})
</script>

<style scoped>
.metric-label {
  color: #64748b;
}
.metric-value {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 700;
}
</style>

