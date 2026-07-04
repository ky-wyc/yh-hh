<template>
  <h2 class="page-title">群管理</h2>
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
          <el-option label="禁用" value="disabled" />
        </el-select>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const groups = ref<any[]>([])

async function load() {
  const { data } = await api.get('/groups')
  groups.value = data
}

async function save(row: any) {
  await api.patch(`/groups/${row.qq_group_id}`, { enabled: row.enabled, reply_mode: row.reply_mode })
  ElMessage.success('已保存')
}

onMounted(load)
</script>

