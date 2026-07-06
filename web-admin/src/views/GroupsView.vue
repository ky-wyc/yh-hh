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

      <h3 class="section-title">基础群管</h3>
      <el-form :model="moderationForm" label-width="120px">
        <el-form-item label="策略模板">
          <el-button-group class="template-group">
            <el-button
              v-for="template in moderationTemplates"
              :key="template.key"
              size="small"
              @click="applyModerationTemplate(template.key)"
            >
              {{ template.label }}
            </el-button>
          </el-button-group>
        </el-form-item>
        <el-form-item label="新人欢迎">
          <el-switch v-model="moderationForm.welcome_enabled" />
        </el-form-item>
        <el-form-item label="欢迎语">
          <el-input
            v-model="moderationForm.welcome_message"
            type="textarea"
            :rows="2"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="刷屏检测">
          <el-switch v-model="moderationForm.flood_enabled" />
        </el-form-item>
        <el-form-item label="消息阈值">
          <el-input-number v-model="moderationForm.flood_message_count" :min="3" :max="50" />
        </el-form-item>
        <el-form-item label="统计窗口秒">
          <el-input-number v-model="moderationForm.flood_window_seconds" :min="3" :max="300" />
        </el-form-item>
        <el-form-item label="禁言秒数">
          <el-input-number v-model="moderationForm.flood_mute_seconds" :min="10" :max="3600" />
        </el-form-item>
        <el-form-item label="累计窗口小时">
          <el-input-number v-model="moderationForm.violation_window_hours" :min="1" :max="168" />
        </el-form-item>
        <el-form-item label="阶梯处罚">
          <el-switch v-model="moderationForm.escalation_enabled" />
        </el-form-item>
        <el-form-item label="处罚倍率">
          <el-input-number v-model="moderationForm.escalation_multiplier" :min="1" :max="5" />
        </el-form-item>
        <el-form-item label="禁言封顶秒">
          <el-input-number v-model="moderationForm.escalation_max_mute_seconds" :min="10" :max="86400" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="savingModeration" @click="saveModeration">保存群管配置</el-button>
        </el-form-item>
      </el-form>

      <h3 class="section-title">近期违规</h3>
      <el-table :data="groupDetail.moderation_stats" border>
        <el-table-column prop="user_id" label="用户 QQ" min-width="140" />
        <el-table-column prop="violation_count" label="累计次数" width="110" />
        <el-table-column label="最近时间" width="190">
          <template #default="{ row }">{{ formatTime(row.last_violation_at) }}</template>
        </el-table-column>
      </el-table>

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
  moderation: {
    welcome_enabled: boolean
    welcome_message: string
    flood_enabled: boolean
    flood_message_count: number
    flood_window_seconds: number
    flood_mute_seconds: number
    violation_window_hours: number
    escalation_enabled: boolean
    escalation_multiplier: number
    escalation_max_mute_seconds: number
  }
  overview: Record<string, number>
  moderation_stats: Array<{
    user_id: string
    violation_count: number
    last_violation_at: string
  }>
  skills: SkillSetting[]
}

type ModerationConfig = GroupDetail['moderation']
type ModerationTemplateKey = 'observe' | 'loose' | 'standard' | 'strict'

const groups = ref<GroupRow[]>([])
const globalSkills = ref<SkillSetting[]>([])
const groupDetail = ref<GroupDetail | null>(null)
const creating = ref(false)
const skillsLoading = ref(false)
const detailVisible = ref(false)
const savingModeration = ref(false)
const newGroup = reactive({
  qq_group_id: '',
  name: '',
  enabled: true,
  reply_mode: 'mention_only'
})
const moderationForm = reactive({
  welcome_enabled: false,
  welcome_message: '欢迎 {user_id} 加入本群。',
  flood_enabled: false,
  flood_message_count: 6,
  flood_window_seconds: 10,
  flood_mute_seconds: 60,
  violation_window_hours: 24,
  escalation_enabled: false,
  escalation_multiplier: 2,
  escalation_max_mute_seconds: 3600
})

const moderationTemplates: Array<{
  key: ModerationTemplateKey
  label: string
  values: Omit<ModerationConfig, 'welcome_enabled' | 'welcome_message'>
}> = [
  {
    key: 'observe',
    label: '观察模式',
    values: {
      flood_enabled: false,
      flood_message_count: 8,
      flood_window_seconds: 10,
      flood_mute_seconds: 60,
      violation_window_hours: 24,
      escalation_enabled: false,
      escalation_multiplier: 2,
      escalation_max_mute_seconds: 3600
    }
  },
  {
    key: 'loose',
    label: '宽松',
    values: {
      flood_enabled: true,
      flood_message_count: 8,
      flood_window_seconds: 10,
      flood_mute_seconds: 60,
      violation_window_hours: 24,
      escalation_enabled: false,
      escalation_multiplier: 2,
      escalation_max_mute_seconds: 3600
    }
  },
  {
    key: 'standard',
    label: '标准',
    values: {
      flood_enabled: true,
      flood_message_count: 6,
      flood_window_seconds: 10,
      flood_mute_seconds: 120,
      violation_window_hours: 24,
      escalation_enabled: true,
      escalation_multiplier: 2,
      escalation_max_mute_seconds: 1800
    }
  },
  {
    key: 'strict',
    label: '严格',
    values: {
      flood_enabled: true,
      flood_message_count: 4,
      flood_window_seconds: 10,
      flood_mute_seconds: 300,
      violation_window_hours: 24,
      escalation_enabled: true,
      escalation_multiplier: 3,
      escalation_max_mute_seconds: 3600
    }
  }
]

const overviewItems = [
  { key: 'messages', label: '消息' },
  { key: 'replies', label: '回复' },
  { key: 'memories', label: '记忆' },
  { key: 'knowledge_docs', label: '知识' },
  { key: 'keyword_rules', label: '关键词' },
  { key: 'scheduled_tasks', label: '任务' },
  { key: 'active_games', label: '游戏' }
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
    Object.assign(moderationForm, data.moderation)
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

async function saveModeration() {
  if (!groupDetail.value) return
  savingModeration.value = true
  try {
    await api.patch(`/groups/${groupDetail.value.qq_group_id}`, { ...moderationForm })
    ElMessage.success('群管配置已保存')
    await openDetail(groupDetail.value.qq_group_id)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存群管配置失败')
  } finally {
    savingModeration.value = false
  }
}

function applyModerationTemplate(key: ModerationTemplateKey) {
  const template = moderationTemplates.find((item) => item.key === key)
  if (!template) return
  Object.assign(moderationForm, template.values)
  ElMessage.success(`已套用${template.label}`)
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

function formatTime(value: string) {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 19)
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

.template-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 0;
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
