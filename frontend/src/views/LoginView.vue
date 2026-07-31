<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { getApiError } from "@/services/api";
import { useAuth } from "@/stores/auth";

const props = withDefaults(
  defineProps<{
    portal?: "employee" | "admin";
  }>(),
  { portal: "employee" },
);

const router = useRouter();
const auth = useAuth();
const loading = ref(false);
const form = reactive({ username: "", password: "" });
const isAdminPortal = computed(() => props.portal === "admin");

async function submit(): Promise<void> {
  loading.value = true;
  try {
    await auth.login(form.username, form.password);
    if (isAdminPortal.value && !auth.isAdmin.value) {
      auth.logout();
      ElMessage.error("该入口仅允许管理员账号登录");
      return;
    }
    if (!isAdminPortal.value && auth.isAdmin.value) {
      ElMessage.success("管理员账号已登录，正在进入管理面板");
      await router.replace("/admin/images");
      return;
    }
    ElMessage.success("登录成功");
    await router.replace(isAdminPortal.value ? "/admin/images" : "/gallery");
  } catch (error) {
    ElMessage.error(getApiError(error));
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page" :class="{ 'admin-login-page': isAdminPortal }">
    <el-card class="login-card">
      <h1>{{ isAdminPortal ? "管理员面板" : "员工图片中心" }}</h1>
      <p class="login-description">
        {{ isAdminPortal ? "管理员账号登录入口" : "员工账号登录入口" }}
      </p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="请输入密码"
          />
        </el-form-item>
        <el-button
          type="primary"
          class="login-button"
          :loading="loading"
          @click="submit"
          >登录</el-button
        >
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: #f5f7fa;
}
.login-card {
  width: 420px;
}
.admin-login-page {
  background: #111827;
}
.login-card h1 {
  margin: 0;
  text-align: center;
  font-size: 24px;
}
.login-description {
  margin: 8px 0 24px;
  color: #6b7280;
  text-align: center;
  font-size: 14px;
}
.login-button {
  width: 100%;
}
</style>
