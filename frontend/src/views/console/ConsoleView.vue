<script setup lang="ts">
import { useRouter } from "vue-router";
import { useAuth } from "@/stores/auth";
import MCPSettingsPanel from "@/components/console/MCPSettingsPanel.vue";
import IntegrationTokensPanel from "@/components/console/IntegrationTokensPanel.vue";

const auth = useAuth();
const router = useRouter();
function logout(): void {
  auth.logout();
  void router.replace({ path: "/admin", query: { redirect: "/console" } });
}
</script>

<template>
  <div class="console-page">
    <header class="console-header">
      <div><h1>MCP 控制台</h1><p>配置连接地址，管理当前账号的集成令牌</p></div>
      <div class="console-actions"><span>{{ auth.user.value?.username }}</span><el-button @click="router.push('/admin/images')">管理员后台</el-button><el-button @click="logout">退出登录</el-button></div>
    </header>
    <main class="console-panels"><MCPSettingsPanel /><IntegrationTokensPanel /></main>
  </div>
</template>

<style scoped>
.console-page { min-height: 100vh; background: #f5f7fa; padding: 24px; box-sizing: border-box; }
.console-header { max-width: 1100px; margin: 0 auto 24px; display: flex; justify-content: space-between; align-items: center; gap: 20px; flex-wrap: wrap; }
h1 { margin: 0 0 8px; font-size: 26px; }
p { margin: 0; color: #6b7280; }
.console-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.console-panels { max-width: 1100px; margin: auto; display: grid; gap: 24px; }
</style>
