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
  await router.replace("/");
}
</script>

<template>
  <el-container class="app-shell">
    <el-aside width="220px" class="app-sidebar">
      <div class="brand">
        {{ auth.isSupervisor.value ? "主管图片中心" : "员工图片中心" }}
      </div>
      <el-menu router :default-active="route.path">
        <el-menu-item index="/gallery">
          {{ auth.isSupervisor.value ? "团队图库" : "我的图库" }}
        </el-menu-item>
        <el-menu-item index="/upload">上传图片</el-menu-item>
        <el-menu-item v-if="auth.isSupervisor.value" index="/team">
          组员管理
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="app-header">
        <div>
          <strong>{{ auth.user.value?.username ?? "员工端" }}</strong>
          <el-tag size="small" type="info" class="header-role">
            {{ auth.isSupervisor.value ? "主管端" : "员工端" }}
          </el-tag>
        </div>
        <el-button link @click="logout">退出登录</el-button>
      </el-header>
      <el-main class="app-main"><RouterView /></el-main>
    </el-container>
  </el-container>
</template>
