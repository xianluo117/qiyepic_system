<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { getApiError } from "@/services/api";
import { loadMCPSettings, saveMCPSettings, type MCPSettings } from "@/services/console";
import { copyConsoleText } from "@/services/consoleClipboard";

const form = reactive({ enabled: false, public_base_url: "" });
const saved = ref<MCPSettings | null>(null);
const loading = ref(false);
const saving = ref(false);
const errorText = ref("");

async function load(): Promise<void> {
  loading.value = true;
  errorText.value = "";
  try {
    saved.value = await loadMCPSettings();
    Object.assign(form, saved.value);
  } catch (error) {
    errorText.value = getApiError(error);
  } finally {
    loading.value = false;
  }
}

function useCurrentAddress(): void {
  form.public_base_url = window.location.origin;
  if (["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname)) {
    ElMessage.warning("当前为本机地址，远程客户端需要使用可访问的域名");
  }
}

async function save(): Promise<void> {
  saving.value = true;
  try {
    saved.value = await saveMCPSettings({ enabled: form.enabled, public_base_url: form.public_base_url });
    Object.assign(form, saved.value);
    ElMessage.success("配置已保存，后续 MCP 请求立即生效");
  } catch (error) {
    ElMessage.error(getApiError(error));
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <el-card v-loading="loading">
    <template #header>
      <div class="settings-header">
        <strong>MCP 设置</strong>
        <el-tag v-if="saved" :type="saved.enabled ? 'success' : 'info'">{{ saved.enabled ? "已启用" : "已关闭" }}</el-tag>
        <el-button text @click="load">刷新</el-button>
      </div>
    </template>
    <el-alert v-if="errorText" :title="errorText" type="error" :closable="false" />
    <el-form v-if="saved" label-position="top" @submit.prevent="save">
      <el-form-item label="启用 MCP">
        <el-switch v-model="form.enabled" :disabled="saving" />
      </el-form-item>
      <el-form-item label="公开基础地址">
        <el-input v-model="form.public_base_url" placeholder="https://你的图床域名" :disabled="saving" />
        <el-button text :disabled="saving" @click="useCurrentAddress">使用当前站点地址</el-button>
        <div class="hint">只填写协议、域名和可选端口，不填写 /mcp/。生产环境使用 HTTPS。</div>
      </el-form-item>
      <el-button type="primary" :loading="saving" @click="save">保存配置</el-button>
    </el-form>
    <el-divider />
    <p>已保存的 MCP 连接地址</p>
    <el-input :model-value="saved?.mcp_url ?? ''" readonly placeholder="保存公开地址后显示">
      <template #append><el-button :disabled="!saved?.mcp_url" @click="copyConsoleText(saved?.mcp_url ?? '')">复制</el-button></template>
    </el-input>
    <p class="hint">客户端选择 Streamable HTTP，请求头填写 Authorization: Bearer 加集成令牌。关闭 MCP 不影响图床网页、上传 API 或公开图片。</p>
  </el-card>
</template>

<style scoped>
.settings-header { display: flex; align-items: center; gap: 12px; }
.hint { color: #6b7280; font-size: 13px; line-height: 1.7; }
</style>
