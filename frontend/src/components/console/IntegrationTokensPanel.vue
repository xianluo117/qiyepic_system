<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { getApiError } from "@/services/api";
import { createIntegrationToken, listIntegrationTokens, revokeIntegrationToken, type IntegrationToken } from "@/services/console";
import { copyConsoleText } from "@/services/consoleClipboard";

const items = ref<IntegrationToken[]>([]);
const loading = ref(false);
const creating = ref(false);
const revoking = ref<number | null>(null);
const secret = ref("");
const showSecret = ref(false);
const errorText = ref("");
const form = reactive({ name: "", scopes: ["images:read"], expires_in_days: 90 });

async function load(): Promise<void> {
  loading.value = true;
  errorText.value = "";
  try { items.value = await listIntegrationTokens(); }
  catch (error) { errorText.value = getApiError(error); }
  finally { loading.value = false; }
}

async function create(): Promise<void> {
  if (!form.name.trim()) { ElMessage.warning("请填写令牌名称"); return; }
  creating.value = true;
  try {
    const result = await createIntegrationToken({ ...form, name: form.name.trim() });
    secret.value = result.token;
    showSecret.value = true;
    form.name = "";
    await load();
  } catch (error) { ElMessage.error(getApiError(error)); }
  finally { creating.value = false; }
}

async function revoke(item: IntegrationToken): Promise<void> {
  try { await ElMessageBox.confirm(`撤销“${item.name}”后，使用它的客户端将无法继续访问。`, "撤销令牌", { type: "warning" }); }
  catch { return; }
  revoking.value = item.id;
  try {
    await revokeIntegrationToken(item.id);
    ElMessage.success("令牌已撤销");
    await load();
  } catch (error) { ElMessage.error(getApiError(error)); }
  finally { revoking.value = null; }
}

function date(value: string): string {
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : value + "Z";
  return new Date(normalized).toLocaleString();
}

onMounted(load);
</script>

<template>
  <el-card>
    <template #header><div class="token-header"><strong>我的集成令牌</strong><el-button text @click="load">刷新</el-button></div></template>
    <el-form label-position="top" @submit.prevent="create">
      <el-form-item label="令牌名称"><el-input v-model="form.name" maxlength="128" placeholder="例如：本机 AI 助手" /></el-form-item>
      <el-form-item label="权限">
        <el-checkbox-group v-model="form.scopes">
          <el-checkbox label="images:read" disabled>查询图片（MCP 必需）</el-checkbox>
          <el-checkbox label="images:upload">上传图片</el-checkbox>
          <el-checkbox label="images:reprocess">重新处理图片</el-checkbox>
        </el-checkbox-group>
      </el-form-item>
      <el-form-item label="有效天数"><el-input-number v-model="form.expires_in_days" :min="1" :max="365" :precision="0" /></el-form-item>
      <el-button type="primary" :loading="creating" @click="create">创建令牌</el-button>
    </el-form>
    <el-divider />
    <el-alert v-if="errorText" :title="errorText" type="error" :closable="false" />
    <el-table v-loading="loading" :data="items" empty-text="暂无集成令牌">
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column label="权限" min-width="220"><template #default="{ row }">{{ row.scopes.join('、') }}</template></el-table-column>
      <el-table-column label="到期时间" min-width="180"><template #default="{ row }">{{ date(row.expires_at) }}</template></el-table-column>
      <el-table-column label="状态" width="100"><template #default="{ row }">{{ row.revoked_at ? '已撤销' : '未撤销' }}</template></el-table-column>
      <el-table-column label="操作" width="90"><template #default="{ row }"><el-button link type="danger" :disabled="!!row.revoked_at" :loading="revoking === row.id" @click="revoke(row)">撤销</el-button></template></el-table-column>
    </el-table>
    <el-dialog v-model="showSecret" title="保存集成令牌" width="min(640px, 94vw)" :close-on-click-modal="false" @closed="secret = ''">
      <el-alert title="完整令牌仅显示这一次，请复制保存。关闭后无法再次查看。" type="warning" :closable="false" />
      <el-input :model-value="secret" type="textarea" :rows="3" readonly class="secret" />
      <template #footer><el-button @click="copyConsoleText(secret)">复制令牌</el-button><el-button type="primary" @click="showSecret = false">已保存，关闭</el-button></template>
    </el-dialog>
  </el-card>
</template>

<style scoped>
.token-header { display: flex; align-items: center; gap: 12px; }
.secret { margin-top: 16px; }
</style>
