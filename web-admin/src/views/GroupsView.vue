<template>
  <h2 class="page-title">群管理</h2>

  <el-card class="toolbar-card">
    <template #header>全局 Skill 开关</template>
    <el-table :data="globalSkills" border v-loading="skillsLoading">
      <el-table-column prop="display_name" label="功能" width="140" />
      <el-table-column prop="description" label="说明" min-width="260" />
      <el-table-column label="启用" width="110">
        <template #default="{ row }">
          <el-switch :model-value="row.global_enabled" @change="toggleGlobalSkill(row, $event)" />
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-card class="toolbar-card">
    <el-form :inline="true" :model="newGroup" class="add-group-form">
      <el-form-item label="群号">
        <el-input v-model="newGroup.qq_group_id" placeholder="输入 QQ 群号" />
      </el-form-item>
      <el-form-item label="名称">
        <el-input v-model="newGroup.name" placeholder="可选" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="newGroup.enabled" />
      </el-form-item>
      <el-form-item label="回复模式">
        <el-select v-model="newGroup.reply_mode">
          <el-option label="只响应命令" value="command_only" />
          <el-option label="命令和 @" value="mention_only" />
          <el-option label="主动回答疑问句" value="active" />
          <el-option label="禁用" value="disabled" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="creating" @click="createGroup">添加群配置</el-button>
      </el-form-item>
    </el-form>
  </el-card>
  <el-table :data="groups" border>
    <el-table-column prop="qq_group_id" label="群号" />
    <el-table-column prop="name" label="名称" />
    <el-table-column label="启用">
      <template #default="{ row }">
        <el-switch v-model="row.enabled" @change="save(row)" />
      </template>
    </el-table-column>
    <el-table-column label="回复模式">
      <template #default="{ row }">
        <el-select v-model="row.reply_mode" @change="save(row)">
          <el-option label="只响应命令" value="command_only" />
          <el-option label="命令和 @" value="mention_only" />
          <el-option label="主动回答疑问句" value="active" />
          <el-option label="禁用" value="disabled" />
        </el-select>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="110" fixed="right">
      <template #default="{ row }">
        <el-button size="small" @click="openDetail(row.qq_group_id)">详情</el-button>
      </template>
    </el-table-column>
  </el-table>

  <el-drawer v-model="detailVisible" size="560px" title="群详情">
    <div v-if="groupDetail" class="detail-panel">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="群号">{{ groupDetail.qq_group_id }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ groupDetail.name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ groupDetail.enabled ? '启用' : '停用' }}</el-descriptions-item>
        <el-descriptions-item label="回复模式">{{ replyModeText(groupDetail.reply_mode) }}</el-descriptions-item>
      </el-descriptions>

      <h3 class="section-title">运营统计</h3>
      <el-row :gutter="12">
        <el-col v-for="item in overviewItems" :key="item.key" :span="8">
          <div class="metric-card">
            <div class="metric-value">{{ groupDetail.overview[item.key] }}</div>
            <div class="metric-label">{{ item.label }}</div>
          </div>
        </el-col>
      </el-row>

      <h3 class="section-title">本群 Skill 开关</h3>
      <el-table :data="groupDetail.skills" border>
        <el-table-column prop="display_name" label="功能" width="130" />
        <el-table-column prop="description" label="说明" min-width="220" />
        <el-table-column label="本群启用" width="120">
          <template #default="{ row }">
            <el-switch
              :disabled="!row.global_enabled"
              :model-value="groupSkillValue(row)"
              @change="toggleGroupSkill(row, $event)"
            />
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

type GroupRow = {
  qq_group_id: string
  name: string
  enabled: boolean
  reply_mode: string
}

type SkillSetting = {
  skill_name: string
  display_name: string
  description: string
  global_enabled: boolean
  group_enabled: boolean | null
  effective_enabled: boolean
}

type GroupDetail = GroupRow & {
  overview: Record<string, number>
  skills: SkillSetting[]
}

const groups = ref<GroupRow[]>([])
const globalSkills = ref<SkillSetting[]>([])
const groupDetail = ref<GroupDetail | null>(null)
const creating = ref(false)
const skillsLoading = ref(false)
const detailVisible = ref(false)
const newGroup = reactive({
  qq_group_id: '',
  name: '',
  enabled: true,
  reply_mode: 'mention_only'
})

const overviewItems = [
  { key: 'messages', label: '消息' },
  { key: 'replies', label: '回复' },
  { key: 'memories', label: '记忆' },
  { key: 'knowledge_docs', label: '知识' },
  { key: 'keyword_rules', label: '关键词' },
  { key: 'scheduled_tasks', label: '任务' }
]

async function load() {
  const { data } = await api.get('/groups')
  groups.value = data
}

async function loadGlobalSkills() {
  skillsLoading.value = true
  try {
    const { data } = await api.get('/skills')
    globalSkills.value = data
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载 Skill 开关失败')
  } finally {
    skillsLoading.value = false
  }
}

async function save(row: GroupRow) {
  try {
    await api.patch(`/groups/${row.qq_group_id}`, { enabled: row.enabled, reply_mode: row.reply_mode })
    ElMessage.success('已保存')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存失败')
    await load()
  }
}

async function openDetail(groupId: string) {
  try {
    const { data } = await api.get(`/groups/${groupId}`)
    groupDetail.value = data
    detailVisible.value = true
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载群详情失败')
  }
}

async function toggleGlobalSkill(skill: SkillSetting, value: string | number | boolean) {
  try {
    const enabled = switchValue(value)
    await api.patch(`/skills/${skill.skill_name}`, { enabled, group_id: '' })
    ElMessage.success(enabled ? '全局功能已启用' : '全局功能已停用')
    await loadGlobalSkills()
    if (groupDetail.value) await openDetail(groupDetail.value.qq_group_id)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '更新 Skill 开关失败')
    await loadGlobalSkills()
  }
}

async function toggleGroupSkill(skill: SkillSetting, value: string | number | boolean) {
  if (!groupDetail.value) return
  try {
    const enabled = switchValue(value)
    await api.patch(`/skills/${skill.skill_name}`, {
      enabled,
      group_id: groupDetail.value.qq_group_id
    })
    ElMessage.success(enabled ? '本群功能已启用' : '本群功能已停用')
    await openDetail(groupDetail.value.qq_group_id)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '更新本群 Skill 开关失败')
    await openDetail(groupDetail.value.qq_group_id)
  }
}

function groupSkillValue(skill: SkillSetting) {
  return skill.group_enabled === null ? skill.global_enabled : skill.group_enabled
}

function switchValue(value: string | number | boolean) {
  return value === true || value === 'true' || value === 1
}

function replyModeText(value: string) {
  const labels: Record<string, string> = {
    command_only: '只响应命令',
    mention_only: '命令和 @',
    active: '主动回答疑问句',
    disabled: '禁用'
  }
  return labels[value] || value
}

async function createGroup() {
  const groupId = newGroup.qq_group_id.trim()
  if (!/^\d+$/.test(groupId)) {
    ElMessage.warning('请输入正确的 QQ 群号')
    return
  }
  creating.value = true
  try {
    await api.patch(`/groups/${groupId}`, {
      enabled: newGroup.enabled,
      reply_mode: newGroup.reply_mode,
      name: newGroup.name.trim() || undefined
    })
    ElMessage.success('已添加群配置')
    newGroup.qq_group_id = ''
    newGroup.name = ''
    await load()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '添加群配置失败')
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  load()
  loadGlobalSkills()
})
</script>

<style scoped>
.toolbar-card {
  margin-bottom: 16px;
}

.add-group-form {
  display: flex;
  flex-wrap: wrap;
  gap: 0 8px;
}

.detail-panel {
  padding-bottom: 24px;
}

.section-title {
  margin: 22px 0 12px;
  font-size: 16px;
}

.metric-card {
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.metric-value {
  font-size: 20px;
  font-weight: 700;
}

.metric-label {
  margin-top: 4px;
  color: #64748b;
  font-size: 13px;
}
</style>
