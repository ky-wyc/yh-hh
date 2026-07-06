<template>
  <h2 class="page-title">定时任务</h2>

  <el-card class="toolbar-card">
    <el-form :inline="true" :model="filters" class="filter-form">
      <el-form-item label="筛选群号">
        <el-input v-model="filters.group_id" clearable placeholder="留空查看全部" />
      </el-form-item>
      <el-form-item>
        <el-button :loading="loading" @click="loadTasks">查询</el-button>
        <el-button @click="resetFilter">重置</el-button>
        <el-button type="primary" plain :loading="runsLoading" @click="loadRuns()">刷新执行历史</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-card class="toolbar-card">
    <el-form :model="form" label-width="110px" class="task-form">
      <el-form-item label="任务名称">
        <el-input v-model="form.name" maxlength="255" show-word-limit />
      </el-form-item>
      <el-form-item label="任务类型">
        <el-select v-model="form.task_type" @change="applyTaskDefaults">
          <el-option label="群提醒" value="reminder_once" />
          <el-option label="每日总结" value="daily_summary" />
          <el-option label="聊天记忆总结" value="memory_summarize" />
          <el-option label="清理上下文" value="cleanup_context" />
          <el-option label="知识库重建" value="knowledge_reindex" />
        </el-select>
      </el-form-item>
      <el-form-item label="调度方式">
        <el-select v-model="form.schedule_type">
          <el-option label="一次性" value="once" />
          <el-option label="每天" value="daily" />
          <el-option label="固定间隔" value="interval" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="showsGroup" label="目标群号">
        <el-select
          v-model="form.group_id"
          filterable
          clearable
          :placeholder="requiresGroup ? '选择 QQ 群' : '留空处理全部'"
        >
          <el-option
            v-for="group in groupOptions"
            :key="group.qq_group_id"
            :label="group.name ? `${group.name} (${group.qq_group_id})` : group.qq_group_id"
            :value="group.qq_group_id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="下次运行">
        <el-date-picker
          v-model="form.next_run_at"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ss"
          placeholder="选择运行时间"
        />
      </el-form-item>
      <el-form-item v-if="form.schedule_type === 'interval'" label="间隔秒数">
        <el-input-number v-model="form.interval_seconds" :min="60" :max="2592000" :step="60" />
      </el-form-item>
      <el-form-item v-if="form.task_type === 'reminder_once'" label="提醒内容">
        <el-input
          v-model="form.message"
          type="textarea"
          :rows="3"
          maxlength="2000"
          show-word-limit
        />
      </el-form-item>
      <el-form-item v-if="form.task_type === 'daily_summary'" label="统计小时">
        <el-input-number v-model="form.hours" :min="1" :max="168" :step="1" />
      </el-form-item>
      <el-form-item v-if="form.task_type === 'memory_summarize'" label="统计小时">
        <el-input-number v-model="form.hours" :min="1" :max="168" :step="1" />
      </el-form-item>
      <el-form-item v-if="form.task_type === 'memory_summarize'" label="消息上限">
        <el-input-number v-model="form.limit" :min="5" :max="200" :step="5" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="saveTask">
          {{ editingId ? '保存修改' : '新增任务' }}
        </el-button>
        <el-button v-if="editingId" @click="resetForm">取消编辑</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-table :data="tasks" border v-loading="loading">
    <el-table-column prop="name" label="任务名称" min-width="150" />
    <el-table-column label="类型" width="110">
      <template #default="{ row }">{{ taskTypeText(row.task_type) }}</template>
    </el-table-column>
    <el-table-column label="调度" width="100">
      <template #default="{ row }">{{ scheduleTypeText(row.schedule_type) }}</template>
    </el-table-column>
    <el-table-column label="目标群" width="140">
      <template #default="{ row }">
        <el-tag v-if="row.group_id" type="info">{{ row.group_id }}</el-tag>
        <span v-else>-</span>
      </template>
    </el-table-column>
    <el-table-column label="启用" width="90">
      <template #default="{ row }">
        <el-switch v-model="row.enabled" @change="toggleTask(row)" />
      </template>
    </el-table-column>
    <el-table-column prop="next_run_at" label="下次运行" width="180">
      <template #default="{ row }">{{ formatTime(row.next_run_at) }}</template>
    </el-table-column>
    <el-table-column prop="last_run_at" label="上次运行" width="180">
      <template #default="{ row }">{{ formatTime(row.last_run_at) }}</template>
    </el-table-column>
    <el-table-column label="操作" width="210" fixed="right">
      <template #default="{ row }">
        <el-button size="small" @click="editTask(row)">编辑</el-button>
        <el-button size="small" type="primary" plain @click="loadRuns(row.id)">历史</el-button>
        <el-button size="small" type="danger" plain @click="deleteTask(row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>

  <h3 class="section-title">执行历史</h3>
  <el-table :data="runs" border v-loading="runsLoading">
    <el-table-column prop="task_id" label="任务 ID" width="90" />
    <el-table-column label="类型" width="110">
      <template #default="{ row }">{{ taskTypeText(row.task_type) }}</template>
    </el-table-column>
    <el-table-column prop="group_id" label="目标群" width="140" />
    <el-table-column label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="row.status === 'success' ? 'success' : 'danger'">{{ row.status }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="result_message" label="结果" min-width="150" show-overflow-tooltip />
    <el-table-column prop="error_message" label="错误" min-width="180" show-overflow-tooltip />
    <el-table-column prop="started_at" label="开始时间" width="180">
      <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

type ScheduledTask = {
  id: number
  name: string
  task_type: string
  schedule_type: string
  group_id: string
  user_id: string
  payload: Record<string, any>
  enabled: boolean
  next_run_at: string | null
  interval_seconds: number
  last_run_at: string | null
  created_by: string
  created_at: string
  updated_at: string
}

type TaskRun = {
  id: number
  task_id: number
  task_type: string
  group_id: string
  status: string
  result_message: string
  error_message: string
  started_at: string
  finished_at: string | null
}

type GroupOption = {
  qq_group_id: string
  name: string
}

const tasks = ref<ScheduledTask[]>([])
const runs = ref<TaskRun[]>([])
const groupOptions = ref<GroupOption[]>([])
const loading = ref(false)
const runsLoading = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)

const filters = reactive({
  group_id: ''
})

const form = reactive({
  name: '',
  task_type: 'reminder_once',
  schedule_type: 'once',
  group_id: '',
  next_run_at: '',
  interval_seconds: 3600,
  message: '',
  hours: 24,
  limit: 50,
  enabled: true
})

const requiresGroup = computed(() => ['reminder_once', 'daily_summary', 'memory_summarize'].includes(form.task_type))
const showsGroup = computed(() => ['reminder_once', 'daily_summary', 'memory_summarize', 'knowledge_reindex'].includes(form.task_type))

function errorText(error: any, fallback: string) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return fallback
}

function validateOptionalGroup(value: string, label: string) {
  if (value.trim() && !/^\d+$/.test(value.trim())) {
    ElMessage.warning(`${label}只能填写数字群号`)
    return false
  }
  return true
}

function validateTaskForm() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写任务名称')
    return false
  }
  if (requiresGroup.value && !form.group_id.trim()) {
    ElMessage.warning('请填写目标群号')
    return false
  }
  if (!validateOptionalGroup(form.group_id, '目标群号')) return false
  if (!form.next_run_at) {
    ElMessage.warning('请选择下次运行时间')
    return false
  }
  if (form.schedule_type === 'interval' && form.interval_seconds < 60) {
    ElMessage.warning('固定间隔不能小于 60 秒')
    return false
  }
  if (form.task_type === 'reminder_once' && !form.message.trim()) {
    ElMessage.warning('请填写提醒内容')
    return false
  }
  return true
}

function buildPayload() {
  if (form.task_type === 'reminder_once') {
    return { message: form.message.trim() }
  }
  if (form.task_type === 'daily_summary') {
    return { hours: form.hours }
  }
  if (form.task_type === 'memory_summarize') {
    return { hours: form.hours, limit: form.limit }
  }
  if (form.task_type === 'knowledge_reindex') {
    return { only_failed: false, include_disabled: false, limit: 100 }
  }
  return {}
}

async function loadTasks() {
  if (!validateOptionalGroup(filters.group_id, '筛选群号')) return

  loading.value = true
  try {
    const params = filters.group_id.trim() ? { group_id: filters.group_id.trim() } : {}
    const { data } = await api.get('/scheduled-tasks', { params })
    tasks.value = data
  } catch (error: any) {
    ElMessage.error(errorText(error, '加载定时任务失败'))
  } finally {
    loading.value = false
  }
}

async function loadRuns(taskId?: number) {
  runsLoading.value = true
  try {
    const params = taskId ? { task_id: taskId } : {}
    const { data } = await api.get('/task-runs', { params })
    runs.value = data
  } catch (error: any) {
    ElMessage.error(errorText(error, '加载执行历史失败'))
  } finally {
    runsLoading.value = false
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
  filters.group_id = ''
  loadTasks()
}

function resetForm() {
  editingId.value = null
  form.name = ''
  form.task_type = 'reminder_once'
  form.schedule_type = 'once'
  form.group_id = ''
  form.next_run_at = ''
  form.interval_seconds = 3600
  form.message = ''
  form.hours = 24
  form.limit = 50
  form.enabled = true
}

function applyTaskDefaults() {
  if (form.task_type === 'daily_summary' || form.task_type === 'memory_summarize') {
    form.schedule_type = 'daily'
    form.hours = form.hours || 24
    form.limit = form.limit || 50
  }
  if (form.task_type === 'cleanup_context') {
    form.group_id = ''
    form.schedule_type = 'interval'
  }
  if (form.task_type === 'knowledge_reindex') {
    form.schedule_type = 'once'
  }
}

async function saveTask() {
  if (!validateTaskForm()) return

  saving.value = true
  const payload = {
    name: form.name.trim(),
    task_type: form.task_type,
    schedule_type: form.schedule_type,
    group_id: showsGroup.value ? form.group_id.trim() : '',
    payload: buildPayload(),
    enabled: form.enabled,
    next_run_at: form.next_run_at,
    interval_seconds: form.schedule_type === 'interval' ? form.interval_seconds : 0
  }
  try {
    if (editingId.value) {
      await api.patch(`/scheduled-tasks/${editingId.value}`, payload)
      ElMessage.success('已保存任务')
    } else {
      await api.post('/scheduled-tasks', payload)
      ElMessage.success('已新增任务')
    }
    resetForm()
    await loadTasks()
  } catch (error: any) {
    ElMessage.error(errorText(error, '保存定时任务失败'))
  } finally {
    saving.value = false
  }
}

function editTask(task: ScheduledTask) {
  editingId.value = task.id
  form.name = task.name
  form.task_type = task.task_type
  form.schedule_type = task.schedule_type
  form.group_id = task.group_id
  form.next_run_at = task.next_run_at ? task.next_run_at.slice(0, 19) : ''
  form.interval_seconds = task.interval_seconds || 3600
  form.message = String(task.payload?.message || '')
  form.hours = Number(task.payload?.hours || 24)
  form.limit = Number(task.payload?.limit || 50)
  form.enabled = task.enabled
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function toggleTask(task: ScheduledTask) {
  try {
    await api.patch(`/scheduled-tasks/${task.id}`, { enabled: task.enabled })
    ElMessage.success(task.enabled ? '任务已启用' : '任务已停用')
  } catch (error: any) {
    ElMessage.error(errorText(error, '更新任务状态失败'))
    await loadTasks()
  }
}

async function deleteTask(task: ScheduledTask) {
  try {
    await ElMessageBox.confirm(`确认删除定时任务「${task.name}」？`, '删除定时任务', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  try {
    await api.delete(`/scheduled-tasks/${task.id}`)
    ElMessage.success('已删除任务')
    if (editingId.value === task.id) resetForm()
    await loadTasks()
  } catch (error: any) {
    ElMessage.error(errorText(error, '删除定时任务失败'))
  }
}

function taskTypeText(value: string) {
  const labels: Record<string, string> = {
    reminder_once: '群提醒',
    daily_summary: '每日总结',
    memory_summarize: '聊天记忆总结',
    cleanup_context: '清理上下文',
    knowledge_reindex: '知识库重建'
  }
  return labels[value] || value
}

function scheduleTypeText(value: string) {
  const labels: Record<string, string> = {
    once: '一次性',
    daily: '每天',
    interval: '固定间隔'
  }
  return labels[value] || value
}

function formatTime(value: string | null) {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 19)
}

onMounted(() => {
  loadTasks()
  loadRuns()
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

.task-form {
  max-width: 960px;
}

.section-title {
  margin: 22px 0 12px;
  font-size: 18px;
}
</style>
