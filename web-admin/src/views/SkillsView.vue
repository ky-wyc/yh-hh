<template>
  <h2 class="page-title">功能管理</h2>

  <el-card class="toolbar-card">
    <template #header>
      <div class="card-header-row">
        <span>全局 Skill</span>
        <el-button :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </template>
    <el-table :data="globalSkills" border v-loading="loading">
      <el-table-column prop="display_name" label="功能" width="120" />
      <el-table-column prop="category" label="分类" width="90" />
      <el-table-column label="命令" min-width="150">
        <template #default="{ row }">
          <el-tag v-for="command in row.commands" :key="command" class="command-tag" type="info">
            /{{ command }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="说明" min-width="220" />
      <el-table-column label="能力" min-width="190">
        <template #default="{ row }">
          <el-tag v-if="row.uses_llm" class="flag-tag" type="warning">LLM</el-tag>
          <el-tag v-if="row.uses_knowledge" class="flag-tag" type="success">知识库</el-tag>
          <el-tag v-if="row.uses_memory" class="flag-tag">记忆</el-tag>
          <el-tag v-if="row.private_supported" class="flag-tag" type="info">私聊</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="风险" width="90">
        <template #default="{ row }">
          <el-tag :type="riskType(row.risk_level)">{{ riskText(row.risk_level) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="全局启用" width="110" fixed="right">
        <template #default="{ row }">
          <el-switch :model-value="row.global_enabled" @change="toggleGlobal(row, $event)" />
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-card class="toolbar-card">
    <template #header>群级 Skill</template>
    <el-form :inline="true" class="filter-form">
      <el-form-item label="作用群">
        <el-select v-model="selectedGroupId" filterable clearable placeholder="选择一个已有群">
          <el-option
            v-for="group in groups"
            :key="group.qq_group_id"
            :label="group.name ? `${group.name} (${group.qq_group_id})` : group.qq_group_id"
            :value="group.qq_group_id"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" plain :disabled="!selectedGroupId" :loading="groupLoading" @click="loadGroupSkills">
          加载群配置
        </el-button>
      </el-form-item>
    </el-form>
    <el-alert
      class="section-alert"
      type="info"
      :closable="false"
      show-icon
      title="群级开关只在全局启用时生效；未单独设置时继承全局状态。"
    />
    <el-table :data="groupSkills" border v-loading="groupLoading">
      <el-table-column prop="display_name" label="功能" width="120" />
      <el-table-column prop="category" label="分类" width="90" />
      <el-table-column prop="description" label="说明" min-width="260" />
      <el-table-column label="继承状态" width="120">
        <template #default="{ row }">
          <el-tag :type="row.global_enabled ? 'success' : 'danger'">
            {{ row.global_enabled ? '全局启用' : '全局停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="本群启用" width="120">
        <template #default="{ row }">
          <el-switch
            :disabled="!selectedGroupId || !row.global_enabled"
            :model-value="groupSkillValue(row)"
            @change="toggleGroup(row, $event)"
          />
        </template>
      </el-table-column>
      <el-table-column label="最终状态" width="120">
        <template #default="{ row }">
          <el-tag :type="row.effective_enabled ? 'success' : 'danger'">
            {{ row.effective_enabled ? '可用' : '关闭' }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

type SkillSetting = {
  skill_name: string
  display_name: string
  description: string
  category: string
  commands: string[]
  risk_level: string
  requires_admin: boolean
  uses_llm: boolean
  uses_knowledge: boolean
  uses_memory: boolean
  private_supported: boolean
  global_enabled: boolean
  group_enabled: boolean | null
  effective_enabled: boolean
}

type GroupOption = {
  qq_group_id: string
  name: string
}

const globalSkills = ref<SkillSetting[]>([])
const groupSkills = ref<SkillSetting[]>([])
const groups = ref<GroupOption[]>([])
const selectedGroupId = ref('')
const loading = ref(false)
const groupLoading = ref(false)

function errorText(error: any, fallback: string) {
  return error?.response?.data?.detail || fallback
}

async function loadAll() {
  loading.value = true
  try {
    const [{ data: skills }, { data: groupRows }] = await Promise.all([
      api.get('/skills'),
      api.get('/groups')
    ])
    globalSkills.value = skills
    groups.value = groupRows
  } catch (error: any) {
    ElMessage.error(errorText(error, '加载功能管理失败'))
  } finally {
    loading.value = false
  }
}

async function loadGroupSkills() {
  if (!selectedGroupId.value) {
    groupSkills.value = []
    return
  }
  groupLoading.value = true
  try {
    const { data } = await api.get('/skills', { params: { group_id: selectedGroupId.value } })
    groupSkills.value = data
  } catch (error: any) {
    ElMessage.error(errorText(error, '加载群级 Skill 失败'))
  } finally {
    groupLoading.value = false
  }
}

async function toggleGlobal(skill: SkillSetting, value: string | number | boolean) {
  const enabled = switchValue(value)
  try {
    await api.patch(`/skills/${skill.skill_name}`, { enabled, group_id: '' })
    ElMessage.success(enabled ? '全局功能已启用' : '全局功能已停用')
    await loadAll()
    if (selectedGroupId.value) await loadGroupSkills()
  } catch (error: any) {
    ElMessage.error(errorText(error, '更新全局 Skill 失败'))
    await loadAll()
  }
}

async function toggleGroup(skill: SkillSetting, value: string | number | boolean) {
  if (!selectedGroupId.value) return
  const enabled = switchValue(value)
  try {
    await api.patch(`/skills/${skill.skill_name}`, {
      enabled,
      group_id: selectedGroupId.value
    })
    ElMessage.success(enabled ? '本群功能已启用' : '本群功能已停用')
    await loadGroupSkills()
  } catch (error: any) {
    ElMessage.error(errorText(error, '更新群级 Skill 失败'))
    await loadGroupSkills()
  }
}

function groupSkillValue(skill: SkillSetting) {
  return skill.group_enabled === null ? skill.global_enabled : skill.group_enabled
}

function switchValue(value: string | number | boolean) {
  return value === true || value === 'true' || value === 1
}

function riskText(value: string) {
  const labels: Record<string, string> = {
    low: '低',
    medium: '中',
    high: '高'
  }
  return labels[value] || value
}

function riskType(value: string) {
  if (value === 'high') return 'danger'
  if (value === 'medium') return 'warning'
  return 'success'
}

onMounted(() => {
  loadAll()
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

.command-tag,
.flag-tag {
  margin: 2px 4px 2px 0;
}

.section-alert {
  margin-bottom: 12px;
}
</style>
