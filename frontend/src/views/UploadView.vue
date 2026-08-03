<script setup lang="ts">
import type {
  UploadFile,
  UploadFiles,
  UploadInstance,
  UploadRawFile,
} from "element-plus";
import { ElMessage } from "element-plus";
import { reactive, ref } from "vue";

import { apiClient, getApiError } from "@/services/api";
import type { UploadFileResult } from "@/types";

const uploadRef = ref<UploadInstance>();
const selectedFiles = ref<UploadFiles>([]);
const loading = ref(false);
const results = ref<UploadFileResult[]>([]);
const form = reactive({ sku: "", ratio: "3:4", minShortSide: 1500 });

function onChange(_: UploadFile, files: UploadFiles): void {
  selectedFiles.value = files;
}
function onRemove(_: UploadFile, files: UploadFiles): void {
  selectedFiles.value = files;
}

async function submit(): Promise<void> {
  if (!form.sku.trim()) {
    ElMessage.warning("请输入货号");
    return;
  }
  if (!selectedFiles.value.length) {
    ElMessage.warning("请选择图片");
    return;
  }
  const [ratioWidth, ratioHeight] = form.ratio.split(":").map(Number);
  const data = new FormData();
  data.append("sku", form.sku.trim());
  data.append("ratio_width", String(ratioWidth));
  data.append("ratio_height", String(ratioHeight));
  data.append("min_short_side_px", String(form.minShortSide));
  selectedFiles.value.forEach((file) =>
    data.append("files", file.raw as UploadRawFile),
  );
  loading.value = true;
  try {
    const response = await apiClient.post<{ results: UploadFileResult[] }>(
      "/images/upload",
      data,
    );
    results.value = response.data.results;
    const successCount = results.value.filter((item) => item.success).length;
    ElMessage.success(`上传完成，成功 ${successCount} 个`);
    uploadRef.value?.clearFiles();
    selectedFiles.value = [];
  } catch (error) {
    ElMessage.error(getApiError(error));
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <section class="page-card">
    <h1 class="page-title">上传图片</h1>
    <el-form label-width="110px" style="max-width: 700px">
      <el-form-item label="货号"><el-input v-model="form.sku" /></el-form-item>
      <el-form-item label="目标比例">
        <el-select v-model="form.ratio" style="width: 220px"
          ><el-option label="1:1" value="1:1" /><el-option
            label="3:4"
            value="3:4" /><el-option label="4:3" value="4:3"
        /></el-select>
      </el-form-item>
      <el-form-item label="最小短边"
        ><el-input-number
          v-model="form.minShortSide"
          :min="1"
          :max="20000"
        /><span style="margin-left: 8px">px</span></el-form-item
      >
      <el-form-item label="选择图片">
        <el-upload
          ref="uploadRef"
          drag
          multiple
          :auto-upload="false"
          accept="image/jpeg,image/png,image/webp"
          @change="onChange"
          @remove="onRemove"
        >
          <div>拖拽图片到这里，或点击选择</div>
          <template #tip
            ><div>文件名保持原名称；同名文件将被拒绝</div></template
          >
        </el-upload>
      </el-form-item>
      <el-form-item
        ><el-button type="primary" :loading="loading" @click="submit"
          >开始上传</el-button
        ></el-form-item
      >
    </el-form>
    <el-table v-if="results.length" :data="results" style="margin-top: 20px">
      <el-table-column prop="filename" label="文件名" /><el-table-column
        label="结果"
        width="100"
        ><template #default="{ row }"
          ><el-tag :type="row.success ? 'success' : 'danger'">{{
            row.success ? "成功" : "失败"
          }}</el-tag></template
        ></el-table-column
      ><el-table-column prop="error" label="说明" />
    </el-table>
  </section>
</template>
