<template>
  <h2 class="page-title">关键词规则</h2>

  <el-card class="toolbar-card">
    <el-form :inline="true" :model="filters" class="filter-form">
      <el-form-item label="筛选群号">
        <el-input v-model="filters.group_id" clearable placeholder="留空查看全部" />
      </el-form-item>
      <el-form-item>
        <el-button :loading="loading" @click="load">查询</el-button>
        <el-button @click="resetFilter">重置</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-card class="toolbar-card">
    <el-form :model="form" label-width="90px" class="rule-form">
      <el-form-item label="作用群">
        <el-input v-model="form.group_id" placeholder="留空为全局规则，或填写 QQ 群号" />
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="form.keyword" maxlength="255" show-word-limit />
      </el-form-item>
      <el-form-item label="回复内容">
        <el-input
          v-model="form.response"
          type="textarea"
          :rows="3"
          maxlength="2000"
          show-word-limit
        />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="saveRule">
          {{ editingId ? '保存修改' : '新增规则' }}
        </el-button>
        <el-button v-if="editingId" @click="resetForm">取消编辑</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-table :data="rules" border v-loading="loading">
    <el-table-column label="作用群" width="150">
      <template #default="{ row }">
        <el-tag v-if="row.group_id" type="info">{{ row.group_id }}</el-tag>
        <el-tag v-else>全局</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="keyword" label="关键词" min-width="160" />
    <el-table-column prop="response" label="回复内容" min-width="260" show-overflow-tooltip />
    <el-table-column label="启用" width="100">
      <template #default="{ row }">
        <el-switch v-model="row.enabled" @change="toggleRule(row)" />
      </template>
    </el-table-column>
    <el-table-column prop="created_by" label="创建来源" width="120" />
    <el-table-column prop="created_at" label="创建时间" width="190">
      <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
    </el-table-column>
    <el-table-column label="操作" width="160" fixed="right">
      <template #default="{ row }">
        <el-button size="small" @click="editRule(row)">编辑</el-button>
        <el-button size="small" type="danger" plain @click="deleteRule(row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

type KeywordRule = {
  id: number
  group_id: string
  keyword: string
  response: string
  enabled: boolean
  created_by: string
  created_at: string
}

const rules = ref<KeywordRule[]>([])
const loading = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)

const filters = reactive({
  group_id: ''
})

const form = reactive({
  group_id: '',
  keyword: '',
  response: '',
  enabled: true
})

function errorText(error: any, fallback: string) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return fallback
}

function validateRuleForm() {
  const groupId = form.group_id.trim()
  if (groupId && !/^\d+$/.test(groupId)) {
    ElMessage.warning('作用群只能填写数字群号，或留空作为全局规则')
    return false
  }
  if (!form.keyword.trim()) {
    ElMessage.warning('请填写关键词')
    return false
  }
  if (!form.response.trim()) {
    ElMessage.warning('请填写回复内容')
    return false
  }
  return true
}

async function load() {
  const groupId = filters.group_id.trim()
  if (groupId && !/^\d+$/.test(groupId)) {
    ElMessage.warning('筛选群号只能填写数字')
    return
  }

  loading.value = true
  try {
    const { data } = await api.get('/keyword-rules', {
      params: groupId ? { group_id: groupId } : {}
    })
    rules.value = data
  } catch (error: any) {
    ElMessage.error(errorText(error, '加载关键词规则失败'))
  } finally {
    loading.value = false
  }
}

function resetFilter() {
  filters.group_id = ''
  load()
}

function resetForm() {
  editingId.value = null
  form.group_id = ''
  form.keyword = ''
  form.response = ''
  form.enabled = true
}

async function saveRule() {
  if (!validateRuleForm()) return

  saving.value = true
  const payload = {
    group_id: form.group_id.trim(),
    keyword: form.keyword.trim(),
    response: form.response.trim(),
    enabled: form.enabled
  }
  try {
    if (editingId.value) {
      await api.patch(`/keyword-rules/${editingId.value}`, payload)
      ElMessage.success('已保存规则')
    } else {
      await api.post('/keyword-rules', payload)
      ElMessage.success('已新增规则')
    }
    resetForm()
    await load()
  } catch (error: any) {
    ElMessage.error(errorText(error, '保存关键词规则失败'))
  } finally {
    saving.value = false
  }
}

function editRule(rule: KeywordRule) {
  editingId.value = rule.id
  form.group_id = rule.group_id
  form.keyword = rule.keyword
  form.response = rule.response
  form.enabled = rule.enabled
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function toggleRule(rule: KeywordRule) {
  try {
    await api.patch(`/keyword-rules/${rule.id}`, { enabled: rule.enabled })
    ElMessage.success(rule.enabled ? '规则已启用' : '规则已停用')
  } catch (error: any) {
    ElMessage.error(errorText(error, '更新规则状态失败'))
    await load()
  }
}

async function deleteRule(rule: KeywordRule) {
  try {
    await ElMessageBox.confirm(`确认删除关键词「${rule.keyword}」？`, '删除关键词规则', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  try {
    await api.delete(`/keyword-rules/${rule.id}`)
    ElMessage.success('已删除规则')
    if (editingId.value === rule.id) resetForm()
    await load()
  } catch (error: any) {
    ElMessage.error(errorText(error, '删除关键词规则失败'))
  }
}

function formatTime(value: string) {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 19)
}

onMounted(load)
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

.rule-form {
  max-width: 900px;
}
</style>
