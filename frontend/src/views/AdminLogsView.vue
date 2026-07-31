<script setup lang="ts">
import { ElMessage } from "element-plus";
import { onMounted, reactive, ref } from "vue";

import { apiClient, getApiError } from "@/services/api";
import type { OperationLog } from "@/types";

const loading = ref(false);
const logs = ref<OperationLog[]>([]);
const filters = reactive({
  category: "",
  status: "",
  employee_id: "",
  keyword: "",
});

const categoryLabels: Record<string, string> = {
  auth: "登录认证",
  user: "账号管理",
  image: "图片操作",
  processing: "图片处理",
};

const statusLabels: Record<string, string> = {
  success: "成功",
  failed: "失败",
  info: "进行中",
};

async function loadLogs(): Promise<void> {
  loading.value = true;
  try {
    const params = Object.fromEntries(
      Object.entries(filters).filter(([, value]) => value),
    );
    logs.value = (
      await apiClient.get<OperationLog[]>("/admin/logs", { params })
    ).data;
  } catch (error) {
    ElMessage.error(getApiError(error));
  } finally {
    loading.value = false;
  }
}

onMounted(loadLogs);
</script>

<template>
  <section class="page-card">
    <div class="page-heading">
      <div>
        <h1 class="page-title">系统日志</h1>
        <p class="page-description">查看登录、账号、图片操作和图片处理结果。</p>
      </div>
      <el-button @click="loadLogs">刷新</el-button>
    </div>
    <el-form inline>
      <el-form-item label="类型">
        <el-select v-model="filters.category" clearable style="width: 140px">
          <el-option label="登录认证" value="auth" />
          <el-option label="账号管理" value="user" />
          <el-option label="图片操作" value="image" />
          <el-option label="图片处理" value="processing" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.status" clearable style="width: 120px">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
          <el-option label="进行中" value="info" />
        </el-select>
      </el-form-item>
      <el-form-item label="员工 ID">
        <el-input v-model="filters.employee_id" clearable />
      </el-form-item>
      <el-form-item label="关键词">
        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="账号、文件名、说明"
        />
      </el-form-item>
      <el-button type="primary" @click="loadLogs">查询</el-button>
    </el-form>
    <el-table :data="logs" v-loading="loading">
      <el-table-column prop="created_at" label="时间" width="180" />
      <el-table-column label="类型" width="110">
        <template #default="{ row }">{{
          categoryLabels[row.category] ?? row.category
        }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag
            :type="
              row.status === 'success'
                ? 'success'
                : row.status === 'failed'
                  ? 'danger'
                  : 'info'
            "
          >
            {{ statusLabels[row.status] ?? row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="actor_username" label="操作账号" width="130" />
      <el-table-column prop="employee_id" label="员工 ID" width="110" />
      <el-table-column
        prop="target"
        label="对象"
        min-width="180"
        show-overflow-tooltip
      />
      <el-table-column
        prop="message"
        label="说明"
        min-width="220"
        show-overflow-tooltip
      />
      <el-table-column
        prop="details"
        label="详情"
        min-width="240"
        show-overflow-tooltip
      />
    </el-table>
    <el-empty v-if="!loading && logs.length === 0" description="暂无日志" />
  </section>
</template>
