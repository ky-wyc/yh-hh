<template>
  <h2 class="page-title">长期记忆</h2>

  <el-card class="toolbar-card">
    <el-form :inline="true" :model="filters" class="filter-form">
      <el-form-item label="状态">
        <el-select v-model="filters.status" clearable placeholder="全部">
          <el-option label="待审核" value="pending" />
          <el-option label="已通过" value="approved" />
          <el-option label="已拒绝" value="rejected" />
          <el-option label="已删除" value="deleted" />
        </el-select>
      </el-form-item>
      <el-form-item label="群号">
        <el-select v-model="filters.group_id" filterable clearable placeholder="留空查看全部">
          <el-option
            v-for="group in groupOptions"
            :key="group.qq_group_id"
            :label="group.name ? `${group.name} (${group.qq_group_id})` : group.qq_group_id"
            :value="group.qq_group_id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="用户 QQ">
        <el-input v-model="filters.user_id" clearable placeholder="留空查看全部" />
      </el-form-item>
      <el-form-item>
        <el-button :loading="loading" @click="load">查询</el-button>
        <el-button @click="resetFilter">重置</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-card class="toolbar-card">
    <el-form :model="form" label-width="90px" class="memory-form">
      <el-form-item label="作用群">
        <el-select v-model="form.group_id" filterable clearable placeholder="留空为全局记忆">
          <el-option
            v-for="group in groupOptions"
            :key="group.qq_group_id"
            :label="group.name ? `${group.name} (${group.qq_group_id})` : group.qq_group_id"
            :value="group.qq_group_id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="用户 QQ">
        <el-input v-model="form.user_id" placeholder="留空为群/全局记忆" />
      </el-form-item>
      <el-form-item label="记忆内容">
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="3"
          maxlength="2000"
          show-word-limit
        />
      </el-form-item>
      <el-form-item label="来源">
        <el-input v-model="form.source" maxlength="64" />
      </el-form-item>
      <el-form-item label="可信度">
        <el-slider v-model="form.confidence" :min="0" :max="1" :step="0.05" show-input />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="form.status">
          <el-option label="待审核" value="pending" />
          <el-option label="已通过" value="approved" />
          <el-option label="已拒绝" value="rejected" />
          <el-option label="已删除" value="deleted" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="saveMemory">
          {{ editingId ? '保存修改' : '新增记忆' }}
        </el-button>
        <el-button v-if="editingId" @click="resetForm">取消编辑</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-table :data="memories" border v-loading="loading">
    <el-table-column label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="作用域" width="180">
      <template #default="{ row }">
        <span>{{ scopeText(row) }}</span>
      </template>
    </el-table-column>
    <el-table-column prop="content" label="记忆内容" min-width="300" show-overflow-tooltip />
    <el-table-column prop="source" label="来源" width="120" />
    <el-table-column prop="confidence" label="可信度" width="100" />
    <el-table-column prop="created_at" label="创建时间" width="190">
      <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
    </el-table-column>
    <el-table-column label="操作" width="260" fixed="right">
      <template #default="{ row }">
        <el-button size="small" @click="editMemory(row)">编辑</el-button>
        <el-button size="small" type="success" plain @click="setStatus(row, 'approved')">通过</el-button>
        <el-button size="small" type="warning" plain @click="setStatus(row, 'rejected')">拒绝</el-button>
        <el-button size="small" type="danger" plain @click="deleteMemory(row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

type Memory = {
  id: number
  group_id: string
  user_id: string
  content: string
  source: string
  confidence: number
  status: string
  created_by: string
  created_at: string
  updated_at: string
}

type GroupOption = {
  qq_group_id: string
  name: string
}

const memories = ref<Memory[]>([])
const groupOptions = ref<GroupOption[]>([])
const loading = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)

const filters = reactive({
  status: '',
  group_id: '',
  user_id: ''
})

const form = reactive({
  group_id: '',
  user_id: '',
  content: '',
  source: 'admin',
  confidence: 0.8,
  status: 'approved'
})

function errorText(error: any, fallback: string) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return fallback
}

function validateOptionalId(value: string, label: string) {
  if (value.trim() && !/^\d+$/.test(value.trim())) {
    ElMessage.warning(`${label}只能填写数字，或留空`)
    return false
  }
  return true
}

function validateMemoryForm() {
  if (!validateOptionalId(form.group_id, '作用群')) return false
  if (!validateOptionalId(form.user_id, '用户 QQ')) return false
  if (!form.content.trim()) {
    ElMessage.warning('请填写记忆内容')
    return false
  }
  if (!form.source.trim()) {
    ElMessage.warning('请填写来源')
    return false
  }
  return true
}

async function load() {
  if (!validateOptionalId(filters.group_id, '群号')) return
  if (!validateOptionalId(filters.user_id, '用户 QQ')) return

  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (filters.status) params.status = filters.status
    if (filters.group_id.trim()) params.group_id = filters.group_id.trim()
    if (filters.user_id.trim()) params.user_id = filters.user_id.trim()
    const { data } = await api.get('/memories', { params })
    memories.value = data
  } catch (error: any) {
    ElMessage.error(errorText(error, '加载记忆失败'))
  } finally {
    loading.value = false
  }
}

async function loadGroups() {
  try {
    const { data } = await api.get('/groups')
    groupOptions.value = data
  } catch (error: any) {
    ElMessage.error(errorText(error, '加载群列表失败'))
  }
}

function resetFilter() {
  filters.status = ''
  filters.group_id = ''
  filters.user_id = ''
  load()
}

function resetForm() {
  editingId.value = null
  form.group_id = ''
  form.user_id = ''
  form.content = ''
  form.source = 'admin'
  form.confidence = 0.8
  form.status = 'approved'
}

async function saveMemory() {
  if (!validateMemoryForm()) return

  saving.value = true
  const payload = {
    group_id: form.group_id.trim(),
    user_id: form.user_id.trim(),
    content: form.content.trim(),
    source: form.source.trim(),
    confidence: form.confidence,
    status: form.status
  }
  try {
    if (editingId.value) {
      await api.patch(`/memories/${editingId.value}`, payload)
      ElMessage.success('已保存记忆')
    } else {
      await api.post('/memories', payload)
      ElMessage.success('已新增记忆')
    }
    resetForm()
    await load()
  } catch (error: any) {
    ElMessage.error(errorText(error, '保存记忆失败'))
  } finally {
    saving.value = false
  }
}

function editMemory(memory: Memory) {
  editingId.value = memory.id
  form.group_id = memory.group_id
  form.user_id = memory.user_id
  form.content = memory.content
  form.source = memory.source
  form.confidence = memory.confidence
  form.status = memory.status
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function setStatus(memory: Memory, status: string) {
  try {
    await api.patch(`/memories/${memory.id}`, { status })
    ElMessage.success('已更新状态')
    await load()
  } catch (error: any) {
    ElMessage.error(errorText(error, '更新状态失败'))
  }
}

async function deleteMemory(memory: Memory) {
  try {
    await ElMessageBox.confirm(`确认删除记忆 #${memory.id}？`, '删除记忆', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  try {
    await api.delete(`/memories/${memory.id}`)
    ElMessage.success('已删除记忆')
    if (editingId.value === memory.id) resetForm()
    await load()
  } catch (error: any) {
    ElMessage.error(errorText(error, '删除记忆失败'))
  }
}

function statusText(status: string) {
  const map: Record<string, string> = {
    pending: '待审核',
    approved: '已通过',
    rejected: '已拒绝',
    deleted: '已删除'
  }
  return map[status] || status
}

function statusTag(status: string) {
  const map: Record<string, string> = {
    pending: 'warning',
    approved: 'success',
    rejected: 'info',
    deleted: 'danger'
  }
  return map[status] || ''
}

function scopeText(memory: Memory) {
  if (memory.group_id && memory.user_id) return `群 ${memory.group_id} / 用户 ${memory.user_id}`
  if (memory.group_id) return `群 ${memory.group_id}`
  if (memory.user_id) return `用户 ${memory.user_id}`
  return '全局'
}

function formatTime(value: string) {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 19)
}

onMounted(() => {
  load()
  loadGroups()
})
</script>

<style scoped>
.toolbar-card {
  margin-bottom: 16px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 0 8px;
}

.memory-form {
  max-width: 900px;
}
</style>
