<template>
  <h2 class="page-title">模型设置</h2>
  <el-card>
    <el-form label-width="130px">
      <el-form-item label="Base URL">
        <el-input v-model="form.base_url" />
      </el-form-item>
      <el-form-item label="API Key">
        <el-input v-model="form.api_key" placeholder="留空则不修改" show-password />
      </el-form-item>
      <el-form-item label="模型">
        <el-input v-model="form.model" />
      </el-form-item>
      <el-form-item label="温度">
        <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" />
      </el-form-item>
      <el-form-item label="最大 Token">
        <el-input-number v-model="form.max_tokens" :min="100" :max="8000" />
      </el-form-item>
      <el-button type="primary" @click="save">保存</el-button>
      <el-button @click="test">测试</el-button>
    </el-form>
  </el-card>

  <h2 class="page-title section-title">Bot 设置</h2>
  <el-card>
    <el-form label-width="130px">
      <el-form-item label="默认启用新群">
        <el-switch v-model="botForm.default_group_enabled" />
      </el-form-item>
      <el-form-item label="默认回复模式">
        <el-select v-model="botForm.default_reply_mode">
          <el-option label="只响应命令" value="command_only" />
          <el-option label="命令和 @" value="mention_only" />
          <el-option label="主动模式" value="active" />
          <el-option label="禁用" value="disabled" />
        </el-select>
      </el-form-item>
      <el-form-item label="命令前缀">
        <el-input v-model="botForm.command_prefix" />
      </el-form-item>
      <el-button type="primary" @click="saveBot">保存 Bot 设置</el-button>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

const form = reactive<any>({})
const botForm = reactive<any>({})

async function load() {
  const [{ data: llm }, { data: bot }] = await Promise.all([
    api.get('/settings/llm'),
    api.get('/settings/bot')
  ])
  Object.assign(form, llm, { api_key: '' })
  Object.assign(botForm, bot)
}

async function save() {
  const payload = { ...form }
  if (!payload.api_key) delete payload.api_key
  await api.patch('/settings/llm', payload)
  ElMessage.success('已保存')
}

async function test() {
  const { data } = await api.post('/settings/llm/test', { prompt: '请回复 pong' })
  ElMessageBox.alert(data.text, `测试结果：${data.status}`)
}

async function saveBot() {
  await api.patch('/settings/bot', botForm)
  ElMessage.success('已保存 Bot 设置')
}

onMounted(load)
</script>

<style scoped>
.section-title {
  margin-top: 24px;
}
</style>
