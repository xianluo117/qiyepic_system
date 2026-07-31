<script setup lang="ts">
import { onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuth } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuth();

onMounted(async () => {
  if (!auth.user.value) await auth.loadCurrentUser();
});

async function logout(): Promise<void> {
  auth.logout();
  await router.replace("/login");
}
</script>

<template>
  <el-container class="app-shell admin-shell">
    <el-aside width="240px" class="app-sidebar admin-sidebar">
      <div class="brand">管理员后台</div>
      <el-menu router :default-active="route.path">
        <el-menu-item index="/admin/images">全部图片</el-menu-item>
        <el-menu-item index="/admin/users">账号管理</el-menu-item>
        <el-menu-item index="/admin/logs">系统日志</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="app-header">
        <div>
          <strong>{{ auth.user.value?.username ?? "管理员" }}</strong>
          <el-tag size="small" type="danger" class="header-role"
            >管理员后台</el-tag
          >
        </div>
        <el-button link @click="logout">退出登录</el-button>
      </el-header>
      <el-main class="app-main"><RouterView /></el-main>
    </el-container>
  </el-container>
</template>
