<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import { apiClient, getApiError } from "@/services/api";
import { useAuth } from "@/stores/auth";
import type { ImageItem, ImagePage, ImageStatus } from "@/types";

type ImageKind = "original" | "processed";
type SortField = "created_at" | "sku" | "filename" | "status";
type SortOrder = "asc" | "desc";

const auth = useAuth();
const loading = ref(false);
const images = ref<ImageItem[]>([]);
const totalImages = ref(0);
const currentPage = ref(1);
const pageSize = ref(50);
const selectedImage = ref<ImageItem | null>(null);
const selectedIds = ref<Set<number>>(new Set());
const selectionAnchorId = ref<number | null>(null);
const previewKind = ref<ImageKind>("original");
const copyKind = ref<ImageKind>("original");
const detailLoading = ref(false);
const detailLoadFailed = ref(false);
const reprocessing = ref(false);
const reprocessDialogVisible = ref(false);
const reprocessItems = ref<ImageItem[]>([]);
const reprocessForm = reactive({
  ratioWidth: 3,
  ratioHeight: 4,
  minShortSidePx: 1500,
});
const previewRequestId = ref(0);
const filters = reactive<{
  sku: string;
  filename: string;
  status: ImageStatus | "";
  employee_id: string;
  sort_by: SortField;
  sort_order: SortOrder;
}>({
  sku: "",
  filename: "",
  status: "",
  employee_id: "",
  sort_by: "created_at",
  sort_order: "desc",
});

const selectedCount = computed(() => selectedIds.value.size);

function canManageImage(item: ImageItem): boolean {
  return (
    auth.isAdmin.value || item.employee_id === auth.user.value?.employee_id
  );
}

const canManageSelectedImage = computed(
  () => Boolean(selectedImage.value) && canManageImage(selectedImage.value!),
);
const selectedManageableImages = computed(() =>
  images.value.filter(
    (item) => selectedIds.value.has(item.id) && canManageImage(item),
  ),
);
const allSelected = computed(
  () =>
    images.value.length > 0 &&
    images.value.every((item) => selectedIds.value.has(item.id)),
);
const selectedStatusText = computed(() => {
  const status = selectedImage.value?.status;
  return status === "pending"
    ? "待处理"
    : status === "processing"
      ? "处理中"
      : status === "success"
        ? "处理成功"
        : status === "failed"
          ? "处理失败"
          : "";
});
const detailPublicUrl = computed(() =>
  selectedImage.value
    ? getPublicUrl(selectedImage.value, previewKind.value)
    : "",
);

function getFilenameWithoutExtension(filename: string): string {
  const extensionIndex = filename.lastIndexOf(".");
  return extensionIndex > 0 ? filename.slice(0, extensionIndex) : filename;
}

function getPublicPath(item: ImageItem, kind: ImageKind): string {
  const employeeId = encodeURIComponent(item.employee_id);
  const sku = encodeURIComponent(item.sku);
  const filename = encodeURIComponent(
    getFilenameWithoutExtension(item.original_filename),
  );
  const path = `/api/public/images/${employeeId}/${sku}/${filename}/${kind}`;
  if (kind !== "processed" || !item.processed_at) return path;

  return `${path}?v=${encodeURIComponent(item.processed_at)}`;
}

function getPublicUrl(item: ImageItem, kind: ImageKind): string {
  return new URL(getPublicPath(item, kind), window.location.origin).href;
}

function resetSelectionForVisibleImages(): void {
  const visibleIds = new Set(images.value.map((item) => item.id));
  selectedIds.value = new Set(
    [...selectedIds.value].filter((id) => visibleIds.has(id)),
  );
}

async function loadImages(): Promise<void> {
  loading.value = true;
  try {
    const params = {
      ...Object.fromEntries(
        Object.entries(filters).filter(([, value]) => value),
      ),
      page: currentPage.value,
      page_size: pageSize.value,
    };
    const { data } = await apiClient.get<ImagePage>("/images", { params });
    images.value = data.items;
    totalImages.value = data.total;
    resetSelectionForVisibleImages();
    const current = selectedImage.value
      ? data.items.find((item) => item.id === selectedImage.value?.id)
      : null;
    selectImage(current ?? data.items[0] ?? null);
  } catch (error) {
    ElMessage.error(getApiError(error));
  } finally {
    loading.value = false;
  }
}

async function submitFilters(): Promise<void> {
  currentPage.value = 1;
  await loadImages();
}

async function changePage(page: number): Promise<void> {
  currentPage.value = page;
  selectedIds.value = new Set<number>();
  selectionAnchorId.value = null;
  await loadImages();
}

async function changePageSize(size: number): Promise<void> {
  pageSize.value = size;
  currentPage.value = 1;
  selectedIds.value = new Set<number>();
  selectionAnchorId.value = null;
  await loadImages();
}

function selectImage(item: ImageItem | null): void {
  selectedImage.value = item;
  previewKind.value = "original";
  detailLoadFailed.value = false;
  detailLoading.value = Boolean(item);
  previewRequestId.value += 1;
}

function switchPreview(kind: ImageKind): void {
  if (!selectedImage.value) return;
  if (kind === "processed" && selectedImage.value.status !== "success") {
    ElMessage.warning("处理图尚未生成");
    return;
  }
  previewKind.value = kind;
  detailLoadFailed.value = false;
  detailLoading.value = true;
  previewRequestId.value += 1;
}

function getImageRequestId(event: Event): number {
  return Number((event.currentTarget as HTMLImageElement).dataset.requestId);
}

function markDetailLoaded(event: Event): void {
  if (getImageRequestId(event) !== previewRequestId.value) return;
  detailLoading.value = false;
  detailLoadFailed.value = false;
}

function markDetailFailed(event: Event): void {
  if (getImageRequestId(event) !== previewRequestId.value) return;
  detailLoading.value = false;
  detailLoadFailed.value = true;
}

function toggleSelected(id: number, checked: boolean): void {
  const next = new Set(selectedIds.value);
  if (checked) next.add(id);
  else next.delete(id);
  selectedIds.value = next;
  selectionAnchorId.value = id;
}

function selectRange(targetId: number, selected: boolean): void {
  const anchorId =
    selectionAnchorId.value ?? selectedImage.value?.id ?? targetId;
  const anchorIndex = images.value.findIndex((item) => item.id === anchorId);
  const targetIndex = images.value.findIndex((item) => item.id === targetId);
  if (anchorIndex < 0 || targetIndex < 0) return;

  const start = Math.min(anchorIndex, targetIndex);
  const end = Math.max(anchorIndex, targetIndex);
  const next = new Set(selectedIds.value);
  for (const item of images.value.slice(start, end + 1)) {
    if (selected) next.add(item.id);
    else next.delete(item.id);
  }
  selectedIds.value = next;
}

function handleCardClick(event: MouseEvent, item: ImageItem): void {
  const modifierKey = event.ctrlKey || event.metaKey;
  if (event.shiftKey) {
    event.preventDefault();
    selectRange(item.id, !modifierKey);
  } else if (modifierKey) {
    event.preventDefault();
    toggleSelected(item.id, !selectedIds.value.has(item.id));
  } else {
    selectionAnchorId.value = item.id;
  }
  selectImage(item);
}

function handleCheckboxClick(event: MouseEvent, item: ImageItem): void {
  if (!event.shiftKey) return;
  event.preventDefault();
  event.stopPropagation();
  selectRange(item.id, !(event.ctrlKey || event.metaKey));
  selectImage(item);
}

function toggleSelectAll(checked: boolean): void {
  selectedIds.value = checked
    ? new Set(images.value.map((item) => item.id))
    : new Set<number>();
  selectionAnchorId.value = checked ? (images.value[0]?.id ?? null) : null;
}

async function writeUrlToClipboard(
  text: string,
  successMessage: string,
): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success(successMessage);
  } catch {
    await ElMessageBox.alert(text, "浏览器无法自动写入剪贴板，请手动复制", {
      confirmButtonText: "关闭",
    });
  }
}

async function copyCurrentUrl(item: ImageItem, kind: ImageKind): Promise<void> {
  if (kind === "processed" && item.status !== "success") {
    ElMessage.warning("处理图尚未生成");
    return;
  }
  await writeUrlToClipboard(
    getPublicUrl(item, kind),
    `已复制当前${kind === "original" ? "原图" : "处理图"} URL`,
  );
}

async function copySelectedUrls(): Promise<void> {
  const selected = images.value.filter((item) =>
    selectedIds.value.has(item.id),
  );
  if (selected.length === 0) {
    ElMessage.warning("请先选择图片");
    return;
  }
  if (copyKind.value === "processed") {
    const unavailable = selected.filter((item) => item.status !== "success");
    if (unavailable.length > 0) {
      const names = unavailable
        .slice(0, 5)
        .map((item) => item.original_filename)
        .join("、");
      ElMessage.error(
        `以下图片尚无处理图：${names}${unavailable.length > 5 ? ` 等 ${unavailable.length} 张` : ""}`,
      );
      return;
    }
  }
  const text = selected
    .map((item) => getPublicUrl(item, copyKind.value))
    .join(",");
  await writeUrlToClipboard(
    text,
    `已复制 ${selected.length} 个${copyKind.value === "original" ? "原图" : "处理图"} URL`,
  );
}

async function download(item: ImageItem, kind: ImageKind): Promise<void> {
  try {
    const { data } = await apiClient.get(`/images/${item.id}/file/${kind}`, {
      params: { v: kind === "processed" ? item.processed_at : item.created_at },
      responseType: "blob",
    });
    const url = URL.createObjectURL(data as Blob);
    const link = document.createElement("a");
    link.href = url;
    link.download =
      kind === "processed"
        ? `${getFilenameWithoutExtension(item.original_filename)}.jpg`
        : item.original_filename;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    ElMessage.error(getApiError(error));
  }
}

function openReprocessDialog(items: ImageItem[]): void {
  if (items.length === 0) {
    ElMessage.warning("没有可重新处理的图片");
    return;
  }
  const first = items[0];
  reprocessItems.value = items;
  reprocessForm.ratioWidth = first.target_ratio_width;
  reprocessForm.ratioHeight = first.target_ratio_height;
  reprocessForm.minShortSidePx = first.min_short_side_px;
  reprocessDialogVisible.value = true;
}

async function submitReprocess(): Promise<void> {
  const items = reprocessItems.value;
  if (items.length === 0) return;

  reprocessing.value = true;
  const payload = {
    ratio_width: reprocessForm.ratioWidth,
    ratio_height: reprocessForm.ratioHeight,
    min_short_side_px: reprocessForm.minShortSidePx,
  };
  const results = await Promise.allSettled(
    items.map((item) => apiClient.post(`/images/${item.id}/retry`, payload)),
  );
  reprocessing.value = false;
  reprocessDialogVisible.value = false;

  const successCount = results.filter(
    (result) => result.status === "fulfilled",
  ).length;
  const failedResults = results.filter(
    (result): result is PromiseRejectedResult => result.status === "rejected",
  );

  if (failedResults.length === 0) {
    ElMessage.success(`已提交 ${successCount} 张图片重新处理`);
  } else {
    const firstError = getApiError(failedResults[0].reason);
    ElMessage.warning(
      `已提交 ${successCount} 张，失败 ${failedResults.length} 张：${firstError}`,
    );
  }
  await loadImages();
}

function reprocessCurrent(item: ImageItem): void {
  openReprocessDialog([item]);
}

function reprocessSelected(): void {
  openReprocessDialog(selectedManageableImages.value);
}

async function remove(item: ImageItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      "确定删除该图片及其处理图吗？公开链接也会立即失效。",
      "删除确认",
      {
        type: "warning",
      },
    );
    await apiClient.delete(`/images/${item.id}`);
    const next = new Set(selectedIds.value);
    next.delete(item.id);
    selectedIds.value = next;
    ElMessage.success("删除成功");
    await loadImages();
  } catch (error) {
    if (error !== "cancel") ElMessage.error(getApiError(error));
  }
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

onMounted(loadImages);
</script>

<template>
  <section class="gallery-page">
    <aside class="gallery-library">
      <div class="library-heading">
        <div>
          <h1 class="page-title">
            {{
              auth.isAdmin.value
                ? "全部图片"
                : auth.isSupervisor.value
                  ? "团队图库"
                  : "我的图库"
            }}
          </h1>
          <p>共 {{ totalImages }} 张图片</p>
        </div>
      </div>

      <el-form class="gallery-filters" label-position="top">
        <el-form-item
          v-if="auth.isAdmin.value || auth.isSupervisor.value"
          label="员工 ID"
        >
          <el-input v-model="filters.employee_id" clearable />
        </el-form-item>
        <div class="filter-row">
          <el-form-item label="货号">
            <el-input v-model="filters.sku" clearable />
          </el-form-item>
          <el-form-item label="文件名">
            <el-input v-model="filters.filename" clearable />
          </el-form-item>
        </div>
        <div class="filter-row">
          <el-form-item label="状态">
            <el-select v-model="filters.status" clearable>
              <el-option label="待处理" value="pending" />
              <el-option label="处理中" value="processing" />
              <el-option label="成功" value="success" />
              <el-option label="失败" value="failed" />
            </el-select>
          </el-form-item>
          <el-form-item label="排序字段">
            <el-select v-model="filters.sort_by">
              <el-option label="上传时间" value="created_at" />
              <el-option label="货号" value="sku" />
              <el-option label="原文件名" value="filename" />
              <el-option label="状态" value="status" />
            </el-select>
          </el-form-item>
        </div>
        <div class="filter-row filter-actions">
          <el-form-item label="排序方向">
            <el-select v-model="filters.sort_order">
              <el-option label="降序" value="desc" />
              <el-option label="升序" value="asc" />
            </el-select>
          </el-form-item>
          <el-button type="primary" :loading="loading" @click="submitFilters"
            >查询</el-button
          >
        </div>
      </el-form>

      <div class="batch-toolbar">
        <el-checkbox
          :model-value="allSelected"
          :indeterminate="selectedCount > 0 && !allSelected"
          @change="toggleSelectAll(Boolean($event))"
          >全选</el-checkbox
        >
        <span>已选 {{ selectedCount }} 张</span>
        <el-radio-group v-model="copyKind" size="small">
          <el-radio-button value="original">原图 URL</el-radio-button>
          <el-radio-button value="processed">处理图 URL</el-radio-button>
        </el-radio-group>
        <el-button
          type="primary"
          size="small"
          :disabled="selectedCount === 0"
          @click="copySelectedUrls"
        >
          复制 URL
        </el-button>
        <el-button
          size="small"
          :loading="reprocessing"
          :disabled="selectedManageableImages.length === 0"
          @click="reprocessSelected"
        >
          批量重新处理
        </el-button>
        <el-button
          v-if="selectedCount"
          link
          size="small"
          @click="toggleSelectAll(false)"
          >清空</el-button
        >
      </div>

      <div v-loading="loading" class="thumbnail-grid">
        <article
          v-for="item in images"
          :key="item.id"
          class="thumbnail-card"
          :class="{
            active: selectedImage?.id === item.id,
            selected: selectedIds.has(item.id),
          }"
          title="单击预览；Ctrl/Cmd 单击切换单张选择；Shift 连续选择；Ctrl/Cmd + Shift 连续取消"
          @click="handleCardClick($event, item)"
        >
          <el-checkbox
            class="thumbnail-checkbox"
            :model-value="selectedIds.has(item.id)"
            @click.stop="handleCheckboxClick($event, item)"
            @change="toggleSelected(item.id, Boolean($event))"
          />
          <span
            class="status-dot"
            :class="item.status"
            :title="item.status"
          ></span>
          <div class="thumbnail-image-wrap">
            <img
              :src="getPublicPath(item, 'original')"
              :alt="item.original_filename"
              loading="lazy"
            />
          </div>
          <div class="thumbnail-info">
            <strong :title="item.original_filename">{{
              item.original_filename
            }}</strong>
            <span>{{ item.sku }} · {{ item.employee_id }}</span>
          </div>
        </article>
        <el-empty
          v-if="!loading && images.length === 0"
          description="暂无图片"
        />
      </div>

      <div v-if="totalImages > 0" class="gallery-pagination">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :total="totalImages"
          :current-page="currentPage"
          :page-size="pageSize"
          :page-sizes="[20, 50, 100, 200]"
          @current-change="changePage"
          @size-change="changePageSize"
        />
      </div>
    </aside>

    <main class="gallery-detail">
      <template v-if="selectedImage">
        <header class="detail-heading">
          <div class="detail-title">
            <strong>{{ selectedImage.original_filename }}</strong>
            <span>{{ selectedImage.sku }} · {{ selectedStatusText }}</span>
          </div>
          <el-radio-group :model-value="previewKind" @change="switchPreview">
            <el-radio-button value="original">原图</el-radio-button>
            <el-radio-button
              value="processed"
              :disabled="selectedImage.status !== 'success'"
              >处理图</el-radio-button
            >
          </el-radio-group>
        </header>

        <div v-loading="detailLoading" class="detail-canvas">
          <img
            v-if="!detailLoadFailed"
            :key="`${selectedImage.id}-${previewKind}-${previewRequestId}`"
            :src="detailPublicUrl"
            :alt="selectedImage.original_filename"
            :data-request-id="previewRequestId"
            @load="markDetailLoaded"
            @error="markDetailFailed"
          />
          <el-result
            v-else
            icon="warning"
            title="图片加载失败"
            sub-title="公开图片文件不存在或暂时无法访问"
          />
        </div>

        <footer class="detail-footer">
          <div class="detail-facts">
            <span
              >原图尺寸<strong
                >{{ selectedImage.original_width ?? "-" }} ×
                {{ selectedImage.original_height ?? "-" }}</strong
              ></span
            >
            <span
              >处理尺寸<strong
                >{{ selectedImage.processed_width ?? "-" }} ×
                {{ selectedImage.processed_height ?? "-" }}</strong
              ></span
            >
            <span
              >目标比例<strong
                >{{ selectedImage.target_ratio_width }} :
                {{ selectedImage.target_ratio_height }}</strong
              ></span
            >
            <span
              >上传时间<strong>{{
                formatDate(selectedImage.created_at)
              }}</strong></span
            >
          </div>
          <div class="detail-actions">
            <el-button @click="copyCurrentUrl(selectedImage, 'original')">
              复制当前原图 URL
            </el-button>
            <el-button
              type="primary"
              :disabled="selectedImage.status !== 'success'"
              @click="copyCurrentUrl(selectedImage, 'processed')"
            >
              复制当前处理图 URL
            </el-button>
            <el-button @click="download(selectedImage, 'original')"
              >下载原图</el-button
            >
            <el-button
              :disabled="selectedImage.status !== 'success'"
              @click="download(selectedImage, 'processed')"
              >下载处理图</el-button
            >
            <el-button
              v-if="canManageSelectedImage"
              type="warning"
              :loading="reprocessing"
              :disabled="
                selectedImage.status === 'pending' ||
                selectedImage.status === 'processing'
              "
              @click="reprocessCurrent(selectedImage)"
              >重新处理</el-button
            >
            <el-button
              v-if="
                selectedImage.status === 'failed' && selectedImage.error_message
              "
              @click="
                ElMessageBox.alert(selectedImage.error_message, '处理失败原因')
              "
              >失败原因</el-button
            >
            <el-button
              v-if="canManageSelectedImage"
              type="danger"
              @click="remove(selectedImage)"
              >删除</el-button
            >
          </div>
        </footer>
      </template>
      <el-empty v-else description="请选择一张图片" />
    </main>

    <el-dialog
      v-model="reprocessDialogVisible"
      title="重新处理参数"
      width="420px"
      :close-on-click-modal="!reprocessing"
      :close-on-press-escape="!reprocessing"
    >
      <el-form label-position="top">
        <div class="reprocess-ratio-row">
          <el-form-item label="比例宽度">
            <el-input-number
              v-model="reprocessForm.ratioWidth"
              :min="1"
              :max="1000"
              :precision="0"
            />
          </el-form-item>
          <el-form-item label="比例高度">
            <el-input-number
              v-model="reprocessForm.ratioHeight"
              :min="1"
              :max="1000"
              :precision="0"
            />
          </el-form-item>
        </div>
        <el-form-item label="最小短边 PX">
          <el-input-number
            v-model="reprocessForm.minShortSidePx"
            :min="1"
            :max="20000"
            :precision="0"
          />
        </el-form-item>
        <p class="reprocess-hint">
          将使用同一组参数重新处理
          {{ reprocessItems.length }} 张图片，并保存为图片的新参数。
        </p>
      </el-form>
      <template #footer>
        <el-button
          :disabled="reprocessing"
          @click="reprocessDialogVisible = false"
        >
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="reprocessing"
          @click="submitReprocess"
        >
          确认重新处理
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.gallery-page {
  height: calc(100vh - 112px);
  min-height: 620px;
  display: grid;
  grid-template-columns: minmax(560px, 58%) minmax(480px, 42%);
  overflow: hidden;
  background: #ffffff;
  border: 1px solid #e4e8ef;
  border-radius: 12px;
}

.gallery-library {
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 22px;
  background: #f8fafc;
  border-right: 1px solid #e4e8ef;
}

.library-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 14px;
}

.library-heading p {
  margin: 6px 0 0;
  color: #8490a4;
  font-size: 13px;
}

.gallery-filters {
  padding: 13px 14px 4px;
  background: #ffffff;
  border: 1px solid #e4e8ef;
  border-radius: 10px;
}

.gallery-filters :deep(.el-form-item) {
  margin-bottom: 10px;
}

.filter-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.filter-actions {
  align-items: end;
}

.filter-actions .el-button {
  margin-bottom: 10px;
}

.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 52px;
  margin: 12px 0;
  padding: 8px 11px;
  color: #657187;
  background: #ffffff;
  border: 1px solid #e4e8ef;
  border-radius: 10px;
  font-size: 13px;
}

.batch-toolbar .el-radio-group {
  margin-left: auto;
}

.thumbnail-grid {
  flex: 1 1 0;
  min-height: 180px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-auto-rows: 224px;
  align-content: start;
  gap: 11px;
  overflow-y: auto;
  padding: 2px 5px 20px 2px;
}

.gallery-pagination {
  flex: 0 0 auto;
  display: flex;
  justify-content: center;
  padding-top: 12px;
  overflow-x: auto;
}

.thumbnail-card {
  position: relative;
  width: 100%;
  height: 224px;
  min-width: 0;
  display: grid;
  grid-template-rows: 180px 40px;
  overflow: hidden;
  user-select: none;
  background: #ffffff;
  border: 2px solid transparent;
  border-radius: 10px;
  box-shadow: 0 3px 12px rgb(31 45 72 / 6%);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.thumbnail-card:hover {
  border-color: #b8ccf3;
}

.thumbnail-card.active {
  border-color: #409eff;
  box-shadow: 0 7px 18px rgb(64 158 255 / 18%);
}

.thumbnail-card.selected::after {
  position: absolute;
  inset: 0;
  content: "";
  pointer-events: none;
  border: 3px solid #67c23a;
  border-radius: 8px;
}

.thumbnail-checkbox {
  position: absolute;
  z-index: 2;
  top: 7px;
  left: 8px;
  padding: 3px 5px;
  background: rgb(255 255 255 / 92%);
  border-radius: 5px;
}

.status-dot {
  position: absolute;
  z-index: 2;
  top: 10px;
  right: 10px;
  width: 10px;
  height: 10px;
  border: 2px solid #ffffff;
  border-radius: 50%;
  box-shadow: 0 1px 4px rgb(0 0 0 / 22%);
}

.status-dot.success {
  background: #25b46b;
}
.status-dot.pending,
.status-dot.processing {
  background: #eaa21a;
}
.status-dot.failed {
  background: #e34c5f;
}

.thumbnail-image-wrap {
  width: 100%;
  height: 180px;
  min-width: 0;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: #e9eef5;
}

.thumbnail-image-wrap img {
  display: block;
  width: auto !important;
  height: auto !important;
  max-width: 100% !important;
  max-height: 100% !important;
  object-fit: contain;
}

.thumbnail-info {
  min-width: 0;
  padding: 6px 10px;
}

.thumbnail-info strong,
.thumbnail-info span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thumbnail-info strong {
  color: #29364c;
  font-size: 12px;
}

.thumbnail-info span {
  margin-top: 5px;
  color: #8792a5;
  font-size: 11px;
}

.gallery-detail {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #ffffff;
}

.detail-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 17px 21px;
  border-bottom: 1px solid #e5e9f0;
}

.detail-title {
  min-width: 0;
}

.detail-title strong,
.detail-title span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-title span {
  margin-top: 5px;
  color: #8390a4;
  font-size: 12px;
}

.detail-canvas {
  flex: 0 0 auto;
  width: 100%;
  height: clamp(360px, calc(100vh - 330px), 560px);
  min-width: 0;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 24px;
  background: #202733;
}

.detail-canvas img {
  display: block;
  width: auto !important;
  height: auto !important;
  max-width: 100% !important;
  max-height: 100% !important;
  object-fit: contain;
  box-shadow: 0 18px 60px rgb(0 0 0 / 35%);
}

.detail-canvas :deep(.el-result__title p),
.detail-canvas :deep(.el-result__subtitle p) {
  color: #ffffff;
}

.detail-footer {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 15px 20px;
  border-top: 1px solid #e5e9f0;
}

.detail-facts {
  display: flex;
  gap: 20px;
  min-width: 0;
}

.detail-facts span {
  color: #8a96a9;
  font-size: 11px;
}

.detail-facts strong {
  display: block;
  margin-top: 4px;
  color: #354158;
  font-size: 13px;
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 7px;
}

.detail-actions .el-button {
  margin-left: 0;
}

.reprocess-ratio-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.reprocess-ratio-row :deep(.el-input-number),
:deep(.el-dialog .el-input-number) {
  width: 100%;
}

.reprocess-hint {
  margin: 0;
  color: #8490a4;
  font-size: 13px;
  line-height: 1.6;
}

@media (max-width: 1320px) {
  .gallery-page {
    grid-template-columns: minmax(520px, 55%) minmax(420px, 45%);
  }

  .gallery-library {
    padding-inline: 14px;
  }

  .thumbnail-grid {
    gap: 8px;
  }

  .detail-facts {
    gap: 12px;
  }
}
</style>
