<template>
  <h2 class="page-title">模型与 API 设置</h2>
  <el-card>
    <el-form label-width="130px">
      <el-form-item label="Provider">
        <el-input v-model="form.provider" />
      </el-form-item>
      <el-form-item label="Base URL">
        <el-input v-model="form.base_url" />
      </el-form-item>
      <el-form-item label="API Key">
        <el-input v-model="form.api_key" placeholder="留空则不修改" show-password />
        <span class="field-hint">{{ form.api_key_configured ? '当前已配置' : '当前未配置' }}</span>
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
      <el-form-item label="超时秒数">
        <el-input-number v-model="form.timeout_seconds" :min="1" :max="300" />
      </el-form-item>
      <el-form-item label="测试 Prompt">
        <el-input
          v-model="testPrompt"
          type="textarea"
          :rows="3"
          maxlength="500"
          show-word-limit
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        <el-button :loading="testing" @click="test">测试模型</el-button>
        <el-button type="danger" plain :loading="clearingKey" @click="clearApiKey">清空 API Key</el-button>
      </el-form-item>
    </el-form>
    <el-alert
      v-if="testResult"
      class="test-result"
      :type="testResult.status === 'success' ? 'success' : 'warning'"
      :title="`测试结果：${testResult.status}`"
      :closable="false"
      show-icon
    >
      <p class="result-meta">模型：{{ testResult.model || '-' }}</p>
      <p class="result-text">{{ testResult.text }}</p>
    </el-alert>
  </el-card>

  <h2 class="page-title section-title">知识库 Embedding 设置</h2>
  <el-card>
    <el-form label-width="130px">
      <el-form-item label="Provider">
        <el-select v-model="embeddingForm.provider">
          <el-option label="本地确定性向量" value="local" />
          <el-option label="OpenAI Compatible" value="openai_compatible" />
        </el-select>
      </el-form-item>
      <el-form-item label="Base URL">
        <el-input
          v-model="embeddingForm.base_url"
          :disabled="embeddingForm.provider === 'local'"
        />
      </el-form-item>
      <el-form-item label="API Key">
        <el-input
          v-model="embeddingForm.api_key"
          placeholder="留空则不修改"
          show-password
          :disabled="embeddingForm.provider === 'local'"
        />
        <span class="field-hint">
          {{ embeddingForm.api_key_configured ? '当前已配置' : '当前未配置' }}
        </span>
      </el-form-item>
      <el-form-item label="Embedding 模型">
        <el-input
          v-model="embeddingForm.model"
          :disabled="embeddingForm.provider === 'local'"
        />
      </el-form-item>
      <el-form-item label="向量维度">
        <el-input-number v-model="embeddingForm.dimensions" :min="16" :max="3072" />
        <span class="field-hint">默认 64；维度变化后需要重建知识库索引</span>
      </el-form-item>
      <el-form-item label="超时秒数">
        <el-input-number v-model="embeddingForm.timeout_seconds" :min="1" :max="300" />
      </el-form-item>
      <el-form-item label="测试文本">
        <el-input
          v-model="embeddingTestText"
          type="textarea"
          :rows="2"
          maxlength="500"
          show-word-limit
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="embeddingSaving" @click="saveEmbedding">保存 Embedding</el-button>
        <el-button :loading="embeddingTesting" @click="testEmbedding">测试 Embedding</el-button>
        <el-button
          type="danger"
          plain
          :disabled="embeddingForm.provider === 'local'"
          :loading="embeddingClearingKey"
          @click="clearEmbeddingApiKey"
        >
          清空 API Key
        </el-button>
      </el-form-item>
    </el-form>
    <el-alert
      v-if="embeddingTestResult"
      class="test-result"
      :type="embeddingTestResult.status === 'success' ? 'success' : 'warning'"
      :title="`测试结果：${embeddingTestResult.status}`"
      :closable="false"
      show-icon
    >
      <p class="result-meta">
        Provider：{{ embeddingTestResult.provider }} /
        模型：{{ embeddingTestResult.model || '-' }} /
        维度：{{ embeddingTestResult.actual_dimensions }}
      </p>
      <p v-if="embeddingTestResult.error" class="result-text">{{ embeddingTestResult.error }}</p>
    </el-alert>
  </el-card>

  <h2 class="page-title section-title">机器人运营设置</h2>
  <el-card>
    <el-form label-width="130px">
      <el-form-item label="机器人 QQ">
        <el-input v-model="botForm.bot_qq" placeholder="用于识别自身消息，可留空使用 OneBot self_id" />
      </el-form-item>
      <el-form-item label="机器人昵称">
        <el-input v-model="botForm.bot_nicknames" placeholder="多个昵称用英文逗号分隔，例如 bot,助手" />
      </el-form-item>
      <el-form-item label="管理员 QQ">
        <el-input v-model="botForm.admin_qq_ids" placeholder="多个 QQ 用英文逗号分隔" />
      </el-form-item>
      <el-form-item label="群白名单">
        <el-input v-model="botForm.allowed_groups" placeholder="多个群号用英文逗号分隔；留空则不限制" />
      </el-form-item>
      <el-form-item label="默认启用新群">
        <el-switch v-model="botForm.default_group_enabled" />
      </el-form-item>
      <el-form-item label="默认回复模式">
        <el-select v-model="botForm.default_reply_mode">
          <el-option label="只响应命令" value="command_only" />
          <el-option label="命令和 @" value="mention_only" />
          <el-option label="主动回答疑问句" value="active" />
          <el-option label="禁用" value="disabled" />
        </el-select>
      </el-form-item>
      <el-form-item label="命令前缀">
        <el-input v-model="botForm.command_prefix" />
      </el-form-item>
      <el-form-item label="用户限流/分钟">
        <el-input-number v-model="botForm.rate_limit_per_user_per_minute" :min="1" :max="600" />
      </el-form-item>
      <el-form-item label="群限流/分钟">
        <el-input-number v-model="botForm.rate_limit_per_group_per_minute" :min="1" :max="3000" />
      </el-form-item>
      <el-button type="primary" :loading="botSaving" @click="saveBot">保存运营设置</el-button>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

const form = reactive<any>({})
const botForm = reactive<any>({})
const embeddingForm = reactive<any>({})
const saving = ref(false)
const testing = ref(false)
const clearingKey = ref(false)
const botSaving = ref(false)
const embeddingSaving = ref(false)
const embeddingTesting = ref(false)
const embeddingClearingKey = ref(false)
const testPrompt = ref('请回复 pong')
const testResult = ref<{ status: string; model: string; text: string } | null>(null)
const embeddingTestText = ref('部署 preflight 检查')
const embeddingTestResult = ref<{
  status: string
  provider: string
  model: string
  dimensions: number
  actual_dimensions: number
  error: string
} | null>(null)

async function load() {
  const [{ data: llm }, { data: bot }, { data: embedding }] = await Promise.all([
    api.get('/settings/llm'),
    api.get('/settings/bot'),
    api.get('/settings/embedding')
  ])
  Object.assign(form, llm, { api_key: '' })
  Object.assign(botForm, bot)
  Object.assign(embeddingForm, embedding, { api_key: '' })
}

async function save() {
  const payload = { ...form }
  if (!payload.api_key) delete payload.api_key
  saving.value = true
  try {
    await api.patch('/settings/llm', payload)
    ElMessage.success('已保存')
    await load()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function test() {
  testing.value = true
  testResult.value = null
  try {
    const { data } = await api.post('/settings/llm/test', { prompt: testPrompt.value })
    testResult.value = data
    if (data.status === 'success') {
      ElMessage.success('模型测试成功')
    } else {
      ElMessage.warning('模型测试未成功，请查看结果')
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '模型测试失败')
  } finally {
    testing.value = false
  }
}

async function clearApiKey() {
  try {
    await ElMessageBox.confirm('清空后模型调用会不可用，直到重新保存新的 API Key。', '清空 API Key', {
      type: 'warning',
      confirmButtonText: '清空',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  clearingKey.value = true
  try {
    await api.patch('/settings/llm', { api_key: '' })
    ElMessage.success('已清空 API Key')
    await load()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '清空 API Key 失败')
  } finally {
    clearingKey.value = false
  }
}

async function saveEmbedding() {
  const payload = { ...embeddingForm }
  if (!payload.api_key) delete payload.api_key
  embeddingSaving.value = true
  try {
    await api.patch('/settings/embedding', payload)
    ElMessage.success('已保存 Embedding 设置')
    await load()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存 Embedding 设置失败')
  } finally {
    embeddingSaving.value = false
  }
}

async function testEmbedding() {
  embeddingTesting.value = true
  embeddingTestResult.value = null
  try {
    const { data } = await api.post('/settings/embedding/test', { text: embeddingTestText.value })
    embeddingTestResult.value = data
    if (data.status === 'success') {
      ElMessage.success('Embedding 测试成功')
    } else {
      ElMessage.warning('Embedding 测试未成功，请查看结果')
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || 'Embedding 测试失败')
  } finally {
    embeddingTesting.value = false
  }
}

async function clearEmbeddingApiKey() {
  try {
    await ElMessageBox.confirm('清空后外部 Embedding 会不可用，直到重新保存新的 API Key。', '清空 Embedding API Key', {
      type: 'warning',
      confirmButtonText: '清空',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  embeddingClearingKey.value = true
  try {
    await api.patch('/settings/embedding', { api_key: '' })
    ElMessage.success('已清空 Embedding API Key')
    await load()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '清空 Embedding API Key 失败')
  } finally {
    embeddingClearingKey.value = false
  }
}

async function saveBot() {
  botSaving.value = true
  try {
    const numericCsvFields = ['admin_qq_ids', 'allowed_groups']
    for (const field of numericCsvFields) {
      const value = String(botForm[field] || '').trim()
      if (value && !/^(\d+)(,\s*\d+)*$/.test(value)) {
        ElMessage.warning('管理员 QQ 和群白名单只能填写数字，并用英文逗号分隔')
        botSaving.value = false
        return
      }
    }
    await api.patch('/settings/bot', botForm)
    ElMessage.success('已保存运营设置')
    await load()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存运营设置失败')
  } finally {
    botSaving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.section-title {
  margin-top: 24px;
}

.test-result {
  margin-top: 18px;
}

.result-meta,
.result-text {
  margin: 6px 0 0;
  line-height: 1.6;
  white-space: pre-wrap;
}

.field-hint {
  margin-left: 12px;
  color: #64748b;
  font-size: 13px;
}
</style>
