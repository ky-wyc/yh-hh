<template>
  <h2 class="page-title">群管理</h2>
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
  </el-table>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const groups = ref<any[]>([])
const creating = ref(false)
const newGroup = reactive({
  qq_group_id: '',
  name: '',
  enabled: true,
  reply_mode: 'mention_only'
})

async function load() {
  const { data } = await api.get('/groups')
  groups.value = data
}

async function save(row: any) {
  try {
    await api.patch(`/groups/${row.qq_group_id}`, { enabled: row.enabled, reply_mode: row.reply_mode })
    ElMessage.success('已保存')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存失败')
    await load()
  }
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

onMounted(load)
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
</style>
