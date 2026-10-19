<!-- frontend/src/views/admin/ModelConfig.vue — 模型配置（在线修改 + 连通性测试） -->
<template>
  <div class="model-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <el-icon><Setting /></el-icon>
          <span>模型配置</span>
          <el-tag v-if="cfg.source === 'db'" size="small" type="success" style="margin-left:6px">来自数据库</el-tag>
          <el-tag v-else size="small" type="info" style="margin-left:6px">来自 .env</el-tag>
          <span class="hint" style="margin-left:auto">保存后立即生效，无需重启服务</span>
        </div>
      </template>

      <!-- 主模型 -->
      <el-divider content-position="left">主模型（合同审查 / 追问 / 法律问答）</el-divider>
      <el-form label-width="110px" class="cfg-form">
        <el-form-item label="模型提供商">
          <el-select v-model="form.llm_provider" style="width:280px" @change="onProviderChange">
            <el-option v-for="p in providers" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
          <span class="tip" v-if="form.llm_provider === 'mock'">不调用外部 API，用于演示与联调</span>
        </el-form-item>

        <el-form-item label="Base URL">
          <el-input v-model="form.llm_base_url" placeholder="如 https://api.siliconflow.cn/v1" style="width:420px" :disabled="form.llm_provider === 'mock'" />
        </el-form-item>

        <el-form-item label="模型名称">
          <el-select
            v-model="form.llm_model" filterable allow-create default-first-option
            style="width:320px" :disabled="form.llm_provider === 'mock'"
            placeholder="选择或直接输入模型名"
          >
            <el-option v-for="m in currentProvider?.models || []" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>

        <el-form-item label="API Key">
          <el-input
            v-model="form.llm_api_key" type="password" show-password
            style="width:420px" :disabled="form.llm_provider === 'mock'"
            :placeholder="cfg.llm_key_set ? `已配置 ${cfg.llm_api_key}，留空表示不修改` : '粘贴 API Key'"
          />
          <span class="tip" v-if="cfg.llm_key_set">留空保留原 Key，输入 <code>-</code> 可清空</span>
        </el-form-item>

        <el-form-item>
          <el-button :loading="testing === 'llm'" :disabled="form.llm_provider === 'mock'" @click="testConn('llm')">
            <el-icon><Connection /></el-icon> 测试连通性
          </el-button>
          <el-button type="primary" :loading="saving" @click="save">保存配置</el-button>
        </el-form-item>
      </el-form>

      <el-alert
        v-if="testResults.llm" :type="testResults.llm.ok ? 'success' : 'error'"
        :closable="false" show-icon style="margin-bottom:12px"
      >
        <template #title>
          <span v-if="testResults.llm.ok">
            连通正常 · {{ testResults.llm.latency_ms }}ms · 模型 {{ testResults.llm.model }}
            <span v-if="testResults.llm.reply">· 返回「{{ testResults.llm.reply }}」</span>
          </span>
          <span v-else>连接失败 · {{ testResults.llm.latency_ms }}ms · {{ testResults.llm.error }}</span>
        </template>
      </el-alert>

      <!-- 视觉模型 -->
      <el-divider content-position="left">视觉模型（图片合同识别，可选）</el-divider>
      <el-form label-width="110px" class="cfg-form">
        <el-form-item label="模型名称">
          <el-select
            v-model="form.vision_model" filterable allow-create clearable default-first-option
            style="width:320px" placeholder="留空则图片合同不可用"
          >
            <el-option v-for="m in currentProvider?.vision_models || []" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="API Key">
          <el-input
            v-model="form.vision_api_key" type="password" show-password style="width:420px"
            :placeholder="cfg.vision_key_set ? `已配置 ${cfg.vision_api_key}，留空继承主模型 Key` : '留空则继承主模型 Key'"
          />
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="form.vision_base_url" placeholder="留空则继承主模型 Base URL" style="width:420px" />
        </el-form-item>
        <el-form-item>
          <el-button :loading="testing === 'vision'" :disabled="!form.vision_model" @click="testConn('vision')">
            测试连通性
          </el-button>
        </el-form-item>
      </el-form>

      <el-alert
        v-if="testResults.vision" :type="testResults.vision.ok ? 'success' : 'error'"
        :closable="false" show-icon
      >
        <template #title>
          <span v-if="testResults.vision.ok">
            连通正常 · {{ testResults.vision.latency_ms }}ms · 模型 {{ testResults.vision.model }}
          </span>
          <span v-else>连接失败 · {{ testResults.vision.latency_ms }}ms · {{ testResults.vision.error }}</span>
        </template>
      </el-alert>

      <!-- Embedding 说明 -->
      <el-divider content-position="left">向量模型（Embedding）</el-divider>
      <el-alert type="info" :closable="false" show-icon>
        <template #title>
          <div class="emb-tip">
            当前由 <code>.env</code> 的 <code>EMBEDDING_PROVIDER</code> 控制（当前：<b>{{ cfg.source === 'db' ? '按 .env' : '按 .env' }}</b>）。
            切换 Embedding 供应商会改变向量维度，必须清空 <code>backend/data/chroma</code> 并重新上传知识文档，
            因此未开放页面修改。如需切换请编辑后端配置后重启。
          </div>
        </template>
      </el-alert>

      <div class="meta" v-if="cfg.updated_at">
        上次修改：{{ fmtTime(cfg.updated_at) }}
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getModelConfig, updateModelConfig, testModelConnection, listModelProviders,
} from '@/api/admin'

const cfg = ref({ llm_key_set: false, vision_key_set: false, source: 'env' })
const providers = ref([])
const saving = ref(false)
const testing = ref('')
const testResults = reactive({ llm: null, vision: null })

const form = reactive({
  llm_provider: 'mock',
  llm_api_key: '',
  llm_model: '',
  llm_base_url: '',
  vision_model: '',
  vision_api_key: '',
  vision_base_url: '',
})

const currentProvider = computed(() => providers.value.find((p) => p.id === form.llm_provider))

function fmtTime(t) {
  return t ? new Date(t).toLocaleString('zh-CN', { hour12: false }) : '-'
}

function fillForm(data) {
  form.llm_provider = data.llm_provider || 'mock'
  form.llm_model = data.llm_model || ''
  form.llm_base_url = data.llm_base_url || ''
  form.vision_model = data.vision_model || ''
  form.vision_base_url = data.vision_base_url || ''
  // 密钥不回填明文，留空表示不修改
  form.llm_api_key = ''
  form.vision_api_key = ''
}

async function load() {
  const [c, ps] = await Promise.all([getModelConfig(), listModelProviders()])
  cfg.value = c
  providers.value = ps
  fillForm(c)
}

function onProviderChange(id) {
  const p = providers.value.find((x) => x.id === id)
  if (!p) return
  if (p.base_url) form.llm_base_url = p.base_url
  if (p.models?.length) form.llm_model = p.models[0]
  testResults.llm = null
}

async function testConn(kind) {
  testing.value = kind
  testResults[kind] = null
  try {
    const payload = kind === 'vision'
      ? {
          provider: form.llm_provider,
          api_key: form.vision_api_key || (cfg.value.vision_key_set ? cfg.value.vision_api_key : ''),
          model: form.vision_model,
          base_url: form.vision_base_url || form.llm_base_url,
          kind: 'vision',
        }
      : {
          provider: form.llm_provider,
          api_key: form.llm_api_key || (cfg.value.llm_key_set ? cfg.value.llm_api_key : ''),
          model: form.llm_model,
          base_url: form.llm_base_url,
          kind: 'llm',
        }
    testResults[kind] = await testModelConnection(payload)
  } catch (e) {
    testResults[kind] = { ok: false, latency_ms: 0, error: e?.message || '测试请求失败' }
  } finally {
    testing.value = ''
  }
}

async function save() {
  saving.value = true
  try {
    const payload = {
      llm_provider: form.llm_provider,
      llm_model: form.llm_model,
      llm_base_url: form.llm_base_url,
      vision_model: form.vision_model,
      vision_base_url: form.vision_base_url,
    }
    // 只有真正输入了才提交密钥（空 = 不修改）
    if (form.llm_api_key) payload.llm_api_key = form.llm_api_key
    if (form.vision_api_key) payload.vision_api_key = form.vision_api_key

    const updated = await updateModelConfig(payload)
    cfg.value = updated
    fillForm(updated)
    ElMessage.success('已保存并立即生效')
  } catch (e) { /* 已提示 */ } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.model-page { max-width: 900px; }
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 700; }
.card-header .hint { font-weight: 400; font-size: 12px; color: #9ca3af; }
.cfg-form { margin-bottom: 4px; }
.tip { margin-left: 10px; font-size: 12px; color: #9ca3af; }
.tip code, .emb-tip code { background: #f1f5f9; padding: 1px 4px; border-radius: 3px; }
.emb-tip { line-height: 1.7; font-size: 13px; }
.meta { margin-top: 14px; font-size: 12px; color: #9ca3af; text-align: right; }
</style>
