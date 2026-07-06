<template>
  <h2 class="page-title">知识库</h2>

  <el-card class="toolbar-card">
    <el-form :inline="true" :model="filters" class="filter-form">
      <el-form-item label="筛选群号">
        <el-input v-model="filters.group_id" clearable placeholder="留空查看全部" />
      </el-form-item>
      <el-form-item label="索引状态">
        <el-select v-model="filters.index_status" clearable placeholder="全部">
          <el-option label="正常" value="vectorized" />
          <el-option label="关键词可用" value="completed" />
          <el-option label="失败" value="failed" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button :loading="loading" @click="load">查询</el-button>
        <el-button @click="resetFilter">重置</el-button>
        <el-button type="primary" plain :loading="bulkReindexing" @click="bulkReindex(false)">
          重建当前筛选
        </el-button>
        <el-button type="warning" plain :loading="retryingFailed" @click="bulkReindex(true)">
          重试失败
        </el-button>
        <el-button type="success" plain :loading="queueingReindex" @click="queueReindex(false)">
          后台重建
        </el-button>
        <el-button type="warning" plain :loading="queueingFailed" @click="queueReindex(true)">
          后台重试失败
        </el-button>
      </el-form-item>
    </el-form>
    <el-alert
      v-if="bulkResult"
      class="bulk-result"
      type="info"
      :closable="false"
      show-icon
      :title="`批量处理：${bulkResult.total} 篇，成功 ${bulkResult.succeeded}，失败 ${bulkResult.failed}，跳过 ${bulkResult.skipped}`"
    />
  </el-card>

  <el-card class="toolbar-card">
    <el-form :inline="true" :model="searchForm" class="filter-form">
      <el-form-item label="测试群号">
        <el-input v-model="searchForm.group_id" placeholder="留空只测全局知识" />
      </el-form-item>
      <el-form-item label="检索问题">
        <el-input v-model="searchForm.query" class="search-input" placeholder="输入关键词或问题" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" plain :loading="searching" @click="searchKnowledge">检索测试</el-button>
      </el-form-item>
    </el-form>
    <el-table v-if="searchResults.length" :data="searchResults" border class="search-table">
      <el-table-column prop="source" label="来源" width="160" />
      <el-table-column prop="content" label="片段" min-width="320" show-overflow-tooltip />
      <el-table-column prop="score" label="分数" width="100" />
    </el-table>
  </el-card>

  <el-card class="toolbar-card">
    <template #header>
      <div class="card-header-row">
        <span>最近索引记录</span>
        <el-button size="small" type="danger" plain :loading="clearingReindexRuns" @click="clearReindexRuns">
          清空记录
        </el-button>
      </div>
    </template>
    <el-table :data="reindexRuns" border v-loading="historyLoading">
      <el-table-column label="类型" width="110">
        <template #default="{ row }">{{ reindexActionText(row.action, row.only_failed) }}</template>
      </el-table-column>
      <el-table-column label="作用群" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.group_id" type="info">{{ row.group_id }}</el-tag>
          <el-tag v-else>全局</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total" label="处理" width="80" />
      <el-table-column prop="succeeded" label="成功" width="80" />
      <el-table-column prop="failed" label="失败" width="80" />
      <el-table-column prop="skipped" label="跳过" width="80" />
      <el-table-column label="结果" width="90">
        <template #default="{ row }">
          <el-tag :type="row.result === 'success' ? 'success' : 'danger'">{{ row.result }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="error_message" label="错误摘要" min-width="180" show-overflow-tooltip />
      <el-table-column label="时间" width="190">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-card class="toolbar-card">
    <template #header>导入文档</template>
    <el-form :model="importForm" label-width="90px" class="knowledge-form">
      <el-form-item label="作用群">
        <el-select
          v-model="importForm.group_ids"
          multiple
          filterable
          clearable
          placeholder="留空为全局知识"
        >
          <el-option
            v-for="group in groupOptions"
            :key="group.qq_group_id"
            :label="group.name ? `${group.name} (${group.qq_group_id})` : group.qq_group_id"
            :value="group.qq_group_id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="标题">
        <el-input v-model="importForm.title" maxlength="255" show-word-limit placeholder="留空使用文件名" />
      </el-form-item>
      <el-form-item label="文件">
        <div class="file-picker">
          <input
            ref="importFileInput"
            class="file-input"
            type="file"
            accept=".txt,.md,.csv,.xlsx,.xlsm"
            @change="selectImportFile"
          />
          <el-button native-type="button" @click="openImportFilePicker">选择文件</el-button>
          <el-tag v-if="importFile" closable @close="removeImportFile">{{ importFile.name }}</el-tag>
          <span v-else class="file-hint">支持 txt、md、csv、xlsx、xlsm</span>
        </div>
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="importForm.enabled" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="importing" @click="importDocument">导入知识库</el-button>
      </el-form-item>
    </el-form>
    <el-alert
      v-if="importReport"
      class="import-report"
      type="success"
      :closable="false"
      show-icon
      :title="`导入完成：生成 ${importReport.created_total} 篇文档，源文件拆分 ${importReport.source_document_count} 篇，导入 ${importReport.imported_row_count || 0} 行，跳过空行 ${importReport.skipped_empty_rows || 0}`"
    />
  </el-card>

  <el-card class="toolbar-card">
    <el-form :model="form" label-width="90px" class="knowledge-form">
      <el-form-item label="作用群">
        <el-input v-model="form.group_id" placeholder="留空为全局知识，或填写 QQ 群号" />
      </el-form-item>
      <el-form-item label="标题">
        <el-input v-model="form.title" maxlength="255" show-word-limit />
      </el-form-item>
      <el-form-item label="正文">
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="8"
          maxlength="200000"
          show-word-limit
        />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="saveDocument">
          {{ editingId ? '保存修改' : '新增文档' }}
        </el-button>
        <el-button v-if="editingId" @click="resetForm">取消编辑</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-table :data="documents" border v-loading="loading">
    <el-table-column label="作用群" width="140">
      <template #default="{ row }">
        <el-tag v-if="row.group_id" type="info">{{ row.group_id }}</el-tag>
        <el-tag v-else>全局</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="title" label="标题" min-width="180" />
    <el-table-column prop="source_file_name" label="来源文件" min-width="180" show-overflow-tooltip />
    <el-table-column prop="source_locator" label="来源位置" min-width="160" show-overflow-tooltip />
    <el-table-column label="启用" width="100">
      <template #default="{ row }">
        <el-switch v-model="row.enabled" @change="toggleDocument(row)" />
      </template>
    </el-table-column>
    <el-table-column prop="chunk_count" label="分块数" width="90" />
    <el-table-column label="索引状态" width="120">
      <template #default="{ row }">
        <el-tag :type="isHealthyIndex(row.index_status) ? 'success' : 'danger'">
          {{ row.index_status }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="index_error" label="索引错误" min-width="180" show-overflow-tooltip />
    <el-table-column prop="updated_at" label="更新时间" width="190">
      <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
    </el-table-column>
    <el-table-column label="操作" width="250" fixed="right">
      <template #default="{ row }">
        <el-button size="small" @click="editDocument(row)">编辑</el-button>
        <el-button size="small" type="primary" plain @click="reindexDocument(row)">重建索引</el-button>
        <el-button size="small" type="danger" plain @click="deleteDocument(row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

type KnowledgeDocument = {
  id: number
  group_id: string
  title: string
  content: string
  source_file_name: string
  source_file_path: string
  source_locator: string
  enabled: boolean
  index_status: string
  index_error: string
  chunk_count: number
  created_by: string
  created_at: string
  updated_at: string
}

type GroupOption = {
  qq_group_id: string
  name: string
}

type SearchResult = {
  source: string
  content: string
  score: number
}

type ReindexRun = {
  id: number
  action: string
  group_id: string
  target_id: string
  total: number
  succeeded: number
  failed: number
  skipped: number
  only_failed: boolean
  include_disabled: boolean
  result: string
  error_message: string
  created_at: string
}

type ImportReport = {
  created_total: number
  source_document_count: number
  source_count: number
  row_count: number
  imported_row_count: number
  skipped_empty_rows: number
  document_count: number
  truncated: boolean
  warnings: string[]
}

const documents = ref<KnowledgeDocument[]>([])
const groupOptions = ref<GroupOption[]>([])
const searchResults = ref<SearchResult[]>([])
const reindexRuns = ref<ReindexRun[]>([])
const importReport = ref<ImportReport | null>(null)
const loading = ref(false)
const historyLoading = ref(false)
const saving = ref(false)
const importing = ref(false)
const clearingReindexRuns = ref(false)
const searching = ref(false)
const bulkReindexing = ref(false)
const retryingFailed = ref(false)
const queueingReindex = ref(false)
const queueingFailed = ref(false)
const editingId = ref<number | null>(null)
const bulkResult = ref<{
  total: number
  succeeded: number
  failed: number
  skipped: number
} | null>(null)

const filters = reactive({
  group_id: '',
  index_status: ''
})

const searchForm = reactive({
  group_id: '',
  query: ''
})

const form = reactive({
  group_id: '',
  title: '',
  content: '',
  enabled: true
})

const importForm = reactive({
  group_ids: [] as string[],
  title: '',
  enabled: true
})
const importFile = ref<File | null>(null)
const importFileInput = ref<HTMLInputElement | null>(null)

function errorText(error: any, fallback: string) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return fallback
}

function validateOptionalGroup(value: string, label: string) {
  if (value.trim() && !/^\d+$/.test(value.trim())) {
    ElMessage.warning(`${label}只能填写数字群号，或留空`)
    return false
  }
  return true
}

function validateDocumentForm() {
  if (!validateOptionalGroup(form.group_id, '作用群')) return false
  if (!form.title.trim()) {
    ElMessage.warning('请填写标题')
    return false
  }
  if (!form.content.trim()) {
    ElMessage.warning('请填写正文')
    return false
  }
  return true
}

async function load() {
  if (!validateOptionalGroup(filters.group_id, '筛选群号')) return

  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (filters.group_id.trim()) params.group_id = filters.group_id.trim()
    if (filters.index_status) params.index_status = filters.index_status
    const { data } = await api.get('/knowledge-docs', { params })
    documents.value = data
    await loadReindexRuns()
  } catch (error: any) {
    ElMessage.error(errorText(error, '加载知识库失败'))
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

async function loadReindexRuns() {
  historyLoading.value = true
  try {
    const params: Record<string, string | number> = { limit: 10 }
    if (filters.group_id.trim()) params.group_id = filters.group_id.trim()
    const { data } = await api.get('/knowledge-docs/reindex-runs', { params })
    reindexRuns.value = data
  } catch (error: any) {
    ElMessage.error(errorText(error, '加载索引记录失败'))
  } finally {
    historyLoading.value = false
  }
}

function openImportFilePicker() {
  importFileInput.value?.click()
}

function selectImportFile(event: Event) {
  const input = event.target as HTMLInputElement
  importFile.value = input.files?.[0] || null
}

function removeImportFile() {
  importFile.value = null
  if (importFileInput.value) {
    importFileInput.value.value = ''
  }
}

async function importDocument() {
  if (!importFile.value) {
    ElMessage.warning('请选择要导入的文件')
    return
  }
  importing.value = true
  try {
    const payload = new FormData()
    payload.append('file', importFile.value)
    payload.append('title', importForm.title.trim())
    payload.append('group_ids', JSON.stringify(importForm.group_ids))
    payload.append('enabled', String(importForm.enabled))
    const { data } = await api.post('/knowledge-docs/import', payload, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    importReport.value = {
      created_total: data.total,
      source_document_count: data.source_document_count,
      source_count: data.report?.source_count || 0,
      row_count: data.report?.row_count || 0,
      imported_row_count: data.report?.imported_row_count || 0,
      skipped_empty_rows: data.report?.skipped_empty_rows || 0,
      document_count: data.report?.document_count || 0,
      truncated: Boolean(data.report?.truncated),
      warnings: data.report?.warnings || []
    }
    ElMessage.success(`已导入 ${data.total} 篇知识库文档`)
    importForm.title = ''
    importForm.group_ids = []
    importForm.enabled = true
    removeImportFile()
    await load()
  } catch (error: any) {
    ElMessage.error(errorText(error, '导入知识库失败'))
  } finally {
    importing.value = false
  }
}

async function clearReindexRuns() {
  if (!validateOptionalGroup(filters.group_id, '筛选群号')) return
  const message = filters.group_id.trim()
    ? `确认清空群 ${filters.group_id.trim()} 的最近索引记录？`
    : '确认清空全部最近索引记录？'
  try {
    await ElMessageBox.confirm(message, '清空索引记录', {
      type: 'warning',
      confirmButtonText: '清空',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  clearingReindexRuns.value = true
  try {
    const params: Record<string, string> = {}
    if (filters.group_id.trim()) params.group_id = filters.group_id.trim()
    const { data } = await api.delete('/knowledge-docs/reindex-runs', { params })
    ElMessage.success(`已清空 ${data.deleted} 条索引记录`)
    await loadReindexRuns()
  } catch (error: any) {
    ElMessage.error(errorText(error, '清空索引记录失败'))
  } finally {
    clearingReindexRuns.value = false
  }
}

function resetFilter() {
  filters.group_id = ''
  filters.index_status = ''
  load()
}

function resetForm() {
  editingId.value = null
  form.group_id = ''
  form.title = ''
  form.content = ''
  form.enabled = true
}

async function saveDocument() {
  if (!validateDocumentForm()) return

  saving.value = true
  const payload = {
    group_id: form.group_id.trim(),
    title: form.title.trim(),
    content: form.content.trim(),
    enabled: form.enabled
  }
  try {
    if (editingId.value) {
      await api.patch(`/knowledge-docs/${editingId.value}`, payload)
      ElMessage.success('已保存文档')
    } else {
      await api.post('/knowledge-docs', payload)
      ElMessage.success('已新增文档')
    }
    resetForm()
    await load()
  } catch (error: any) {
    ElMessage.error(errorText(error, '保存知识库文档失败'))
  } finally {
    saving.value = false
  }
}

function editDocument(document: KnowledgeDocument) {
  editingId.value = document.id
  form.group_id = document.group_id
  form.title = document.title
  form.content = document.content
  form.enabled = document.enabled
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function toggleDocument(document: KnowledgeDocument) {
  try {
    await api.patch(`/knowledge-docs/${document.id}`, { enabled: document.enabled })
    ElMessage.success(document.enabled ? '文档已启用' : '文档已停用')
  } catch (error: any) {
    ElMessage.error(errorText(error, '更新文档状态失败'))
    await load()
  }
}

async function reindexDocument(document: KnowledgeDocument) {
  try {
    await api.post(`/knowledge-docs/${document.id}/reindex`)
    ElMessage.success('已重建索引')
    await load()
  } catch (error: any) {
    ElMessage.error(errorText(error, '重建索引失败'))
  }
}

async function bulkReindex(onlyFailed: boolean) {
  if (!validateOptionalGroup(filters.group_id, '筛选群号')) return
  const title = onlyFailed ? '重试失败索引' : '批量重建索引'
  const message = onlyFailed
    ? '将重试当前群号筛选下所有失败文档，是否继续？'
    : '将重建当前群号筛选下所有已启用文档索引，是否继续？'
  try {
    await ElMessageBox.confirm(message, title, {
      type: 'warning',
      confirmButtonText: '继续',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  bulkResult.value = null
  if (onlyFailed) retryingFailed.value = true
  else bulkReindexing.value = true
  try {
    const { data } = await api.post('/knowledge-docs/reindex', {
      group_id: filters.group_id.trim(),
      only_failed: onlyFailed,
      include_disabled: false,
      limit: 100
    })
    bulkResult.value = data
    if (data.failed > 0) {
      ElMessage.warning(`处理完成，但有 ${data.failed} 篇失败`)
    } else {
      ElMessage.success('批量索引处理完成')
    }
    await load()
  } catch (error: any) {
    ElMessage.error(errorText(error, '批量索引处理失败'))
  } finally {
    retryingFailed.value = false
    bulkReindexing.value = false
  }
}

async function queueReindex(onlyFailed: boolean) {
  if (!validateOptionalGroup(filters.group_id, '筛选群号')) return
  const title = onlyFailed ? '后台重试失败索引' : '后台批量重建索引'
  const message = onlyFailed
    ? '将把当前群号筛选下的失败文档加入后台重试队列，是否继续？'
    : '将把当前群号筛选下的已启用文档加入后台重建队列，是否继续？'
  try {
    await ElMessageBox.confirm(message, title, {
      type: 'warning',
      confirmButtonText: '加入队列',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  if (onlyFailed) queueingFailed.value = true
  else queueingReindex.value = true
  try {
    await api.post('/knowledge-docs/reindex-queue', {
      group_id: filters.group_id.trim(),
      only_failed: onlyFailed,
      include_disabled: false,
      limit: 500
    })
    ElMessage.success('已加入后台队列，可在定时任务执行历史查看进度')
  } catch (error: any) {
    ElMessage.error(errorText(error, '加入后台队列失败'))
  } finally {
    queueingFailed.value = false
    queueingReindex.value = false
  }
}

async function deleteDocument(document: KnowledgeDocument) {
  try {
    await ElMessageBox.confirm(`确认删除知识库文档「${document.title}」？`, '删除知识库文档', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  try {
    await api.delete(`/knowledge-docs/${document.id}`)
    ElMessage.success('已删除文档')
    if (editingId.value === document.id) resetForm()
    await load()
  } catch (error: any) {
    ElMessage.error(errorText(error, '删除知识库文档失败'))
  }
}

async function searchKnowledge() {
  if (!validateOptionalGroup(searchForm.group_id, '测试群号')) return
  if (!searchForm.query.trim()) {
    ElMessage.warning('请输入检索问题')
    return
  }

  searching.value = true
  searchResults.value = []
  try {
    const { data } = await api.post('/knowledge-search', {
      group_id: searchForm.group_id.trim(),
      query: searchForm.query.trim()
    })
    searchResults.value = data.results
    if (!searchResults.value.length) {
      ElMessage.warning('没有检索到相关片段')
    }
  } catch (error: any) {
    ElMessage.error(errorText(error, '检索测试失败'))
  } finally {
    searching.value = false
  }
}

function formatTime(value: string) {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 19)
}

function isHealthyIndex(value: string) {
  return value === 'completed' || value === 'vectorized'
}

function reindexActionText(action: string, onlyFailed: boolean) {
  if (action === 'knowledge_doc_reindex') return '单篇重建'
  if (onlyFailed) return '重试失败'
  return '批量重建'
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

.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 0 8px;
}

.knowledge-form {
  max-width: 980px;
}

.file-picker {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.file-input {
  display: none;
}

.file-hint {
  color: #64748b;
  font-size: 13px;
}

.search-input {
  width: 320px;
}

.search-table {
  margin-top: 12px;
}

.bulk-result {
  margin-top: 12px;
}

.import-report {
  margin-top: 12px;
}
</style>
