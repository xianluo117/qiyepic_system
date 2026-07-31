<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { onMounted, reactive, ref } from "vue";

import { apiClient, getApiError } from "@/services/api";
import { useAuth } from "@/stores/auth";
import type { ImageItem, ImageStatus } from "@/types";

const auth = useAuth();
const loading = ref(false);
const images = ref<ImageItem[]>([]);
const filters = reactive<{
  sku: string;
  filename: string;
  status: ImageStatus | "";
  employee_id: string;
}>({
  sku: "",
  filename: "",
  status: "",
  employee_id: "",
});

async function loadImages(): Promise<void> {
  loading.value = true;
  try {
    const params = Object.fromEntries(
      Object.entries(filters).filter(([, value]) => value),
    );
    const { data } = await apiClient.get<ImageItem[]>("/images", { params });
    images.value = data;
  } catch (error) {
    ElMessage.error(getApiError(error));
  } finally {
    loading.value = false;
  }
}

async function download(
  item: ImageItem,
  kind: "original" | "processed",
): Promise<void> {
  try {
    const { data } = await apiClient.get(`/images/${item.id}/file/${kind}`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(data as Blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = item.original_filename;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    ElMessage.error(getApiError(error));
  }
}

async function retry(id: number): Promise<void> {
  try {
    await apiClient.post(`/images/${id}/retry`);
    ElMessage.success("已重新处理");
    await loadImages();
  } catch (error) {
    ElMessage.error(getApiError(error));
  }
}

async function remove(id: number): Promise<void> {
  try {
    await ElMessageBox.confirm("确定删除该图片及其处理图吗？", "删除确认", {
      type: "warning",
    });
    await apiClient.delete(`/images/${id}`);
    ElMessage.success("删除成功");
    await loadImages();
  } catch (error) {
    if (error !== "cancel") ElMessage.error(getApiError(error));
  }
}

onMounted(loadImages);
</script>

<template>
  <section class="page-card">
    <div class="page-heading">
      <div>
        <h1 class="page-title">
          {{ auth.isAdmin.value ? "全部图片" : "我的图库" }}
        </h1>
        <p class="page-description">
          {{
            auth.isAdmin.value
              ? "查看并管理所有员工上传的图片。"
              : "仅显示当前账号上传的图片。"
          }}
        </p>
      </div>
    </div>
    <el-form inline>
      <el-form-item label="员工 ID" v-if="auth.isAdmin.value"
        ><el-input v-model="filters.employee_id" clearable
      /></el-form-item>
      <el-form-item label="货号"
        ><el-input v-model="filters.sku" clearable
      /></el-form-item>
      <el-form-item label="文件名"
        ><el-input v-model="filters.filename" clearable
      /></el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.status" clearable style="width: 140px">
          <el-option label="待处理" value="pending" /><el-option
            label="处理中"
            value="processing"
          />
          <el-option label="成功" value="success" /><el-option
            label="失败"
            value="failed"
          />
        </el-select>
      </el-form-item>
      <el-button type="primary" @click="loadImages">查询</el-button>
    </el-form>
    <el-table :data="images" v-loading="loading">
      <el-table-column prop="employee_id" label="员工" width="110" />
      <el-table-column prop="sku" label="货号" width="150" />
      <el-table-column
        prop="original_filename"
        label="文件名"
        min-width="220"
      />
      <el-table-column label="比例" width="90"
        ><template #default="{ row }"
          >{{ row.target_ratio_width }}:{{ row.target_ratio_height }}</template
        ></el-table-column
      >
      <el-table-column label="状态" width="110">
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
            {{
              row.status === "pending"
                ? "待处理"
                : row.status === "processing"
                  ? "处理中"
                  : row.status === "success"
                    ? "成功"
                    : "失败"
            }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="尺寸" width="170"
        ><template #default="{ row }"
          >{{ row.processed_width ?? "-" }} ×
          {{ row.processed_height ?? "-" }}</template
        ></el-table-column
      >
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="download(row, 'original')"
            >原图</el-button
          >
          <el-button
            link
            type="primary"
            :disabled="row.status !== 'success'"
            @click="download(row, 'processed')"
            >处理图</el-button
          >
          <el-button
            v-if="row.status === 'failed'"
            link
            type="warning"
            @click="retry(row.id)"
            >重试</el-button
          >
          <el-button
            v-if="row.status === 'failed' && row.error_message"
            link
            type="danger"
            @click="ElMessageBox.alert(row.error_message, '处理失败原因')"
            >原因</el-button
          >
          <el-button link type="danger" @click="remove(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && images.length === 0" description="暂无图片" />
  </section>
</template>
