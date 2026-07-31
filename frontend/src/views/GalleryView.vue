<script setup lang="ts">
import { Picture } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { onBeforeUnmount, onMounted, reactive, ref } from "vue";

import { apiClient, getApiError } from "@/services/api";
import { useAuth } from "@/stores/auth";
import type { ImageItem, ImageStatus } from "@/types";

type PreviewKind = "original" | "processed";

const auth = useAuth();
const loading = ref(false);
const images = ref<ImageItem[]>([]);
const previewVisible = ref(false);
const previewLoading = ref(false);
const previewUrl = ref("");
const previewTitle = ref("");
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

async function getImageBlob(item: ImageItem, kind: PreviewKind): Promise<Blob> {
  const { data } = await apiClient.get(`/images/${item.id}/file/${kind}`, {
    responseType: "blob",
  });
  return data as Blob;
}

function clearPreviewUrl(): void {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = "";
  }
}

async function preview(item: ImageItem, kind: PreviewKind): Promise<void> {
  previewVisible.value = true;
  previewLoading.value = true;
  previewTitle.value = `${kind === "original" ? "原图" : "处理图"} · ${item.original_filename}`;
  clearPreviewUrl();
  try {
    previewUrl.value = URL.createObjectURL(await getImageBlob(item, kind));
  } catch (error) {
    previewVisible.value = false;
    ElMessage.error(getApiError(error));
  } finally {
    previewLoading.value = false;
  }
}

function closePreview(): void {
  previewVisible.value = false;
  clearPreviewUrl();
}

async function download(item: ImageItem, kind: PreviewKind): Promise<void> {
  try {
    const url = URL.createObjectURL(await getImageBlob(item, kind));
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
onBeforeUnmount(clearPreviewUrl);
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
      <el-table-column label="预览" width="112">
        <template #default="{ row }">
          <button
            class="thumbnail-button"
            type="button"
            title="预览图片"
            @click="
              preview(row, row.status === 'success' ? 'processed' : 'original')
            "
          >
            <el-icon :size="24"><Picture /></el-icon>
          </button>
        </template>
      </el-table-column>
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
      <el-table-column label="操作" width="390" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="preview(row, 'original')"
            >预览原图</el-button
          >
          <el-button
            link
            type="primary"
            :disabled="row.status !== 'success'"
            @click="preview(row, 'processed')"
            >预览处理图</el-button
          >
          <el-dropdown trigger="click">
            <el-button link type="primary" class="download-button"
              >下载</el-button
            >
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="download(row, 'original')"
                  >下载原图</el-dropdown-item
                >
                <el-dropdown-item
                  :disabled="row.status !== 'success'"
                  @click="download(row, 'processed')"
                  >下载处理图</el-dropdown-item
                >
              </el-dropdown-menu>
            </template>
          </el-dropdown>
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

    <el-dialog
      v-model="previewVisible"
      :title="previewTitle"
      width="min(92vw, 1100px)"
      destroy-on-close
      @closed="closePreview"
    >
      <div v-loading="previewLoading" class="preview-stage">
        <img v-if="previewUrl" :src="previewUrl" :alt="previewTitle" />
      </div>
    </el-dialog>
  </section>
</template>

<style scoped>
.thumbnail-button {
  width: 72px;
  height: 54px;
  display: grid;
  place-items: center;
  color: #409eff;
  background: #f0f7ff;
  border: 1px solid #d9ecff;
  border-radius: 6px;
  cursor: pointer;
}

.thumbnail-button:hover {
  color: #ffffff;
  background: #409eff;
}

.download-button {
  margin-left: 12px;
}

.preview-stage {
  min-height: 360px;
  display: grid;
  place-items: center;
  overflow: auto;
  background: #f5f7fa;
  border-radius: 6px;
}

.preview-stage img {
  display: block;
  max-width: 100%;
  max-height: 72vh;
  object-fit: contain;
}
</style>
