<script setup lang="ts">
import { ElMessage } from "element-plus";
import { onMounted, reactive, ref } from "vue";

import { apiClient, getApiError } from "@/services/api";
import type { User, UserRole } from "@/types";

const users = ref<User[]>([]);
const loading = ref(false);
const dialogVisible = ref(false);
const form = reactive<{
  employee_id: string;
  username: string;
  password: string;
  role: UserRole;
}>({ employee_id: "", username: "", password: "", role: "employee" });

async function loadUsers(): Promise<void> {
  loading.value = true;
  try {
    users.value = (await apiClient.get<User[]>("/users")).data;
  } catch (error) {
    ElMessage.error(getApiError(error));
  } finally {
    loading.value = false;
  }
}

async function createUser(): Promise<void> {
  try {
    await apiClient.post("/users", form);
    ElMessage.success("员工创建成功");
    dialogVisible.value = false;
    Object.assign(form, {
      employee_id: "",
      username: "",
      password: "",
      role: "employee",
    });
    await loadUsers();
  } catch (error) {
    ElMessage.error(getApiError(error));
  }
}

async function toggleUser(user: User): Promise<void> {
  try {
    await apiClient.patch(`/users/${user.id}`, { is_active: !user.is_active });
    await loadUsers();
  } catch (error) {
    ElMessage.error(getApiError(error));
  }
}

async function resetPassword(user: User): Promise<void> {
  const password = window.prompt(
    `请输入 ${user.username} 的新密码（至少 8 位）`,
  );
  if (!password) return;
  try {
    await apiClient.patch(`/users/${user.id}`, { password });
    ElMessage.success("密码已重置");
  } catch (error) {
    ElMessage.error(getApiError(error));
  }
}

onMounted(loadUsers);
</script>

<template>
  <section class="page-card">
    <div class="users-header">
      <h1 class="page-title">员工管理</h1>
      <el-button type="primary" @click="dialogVisible = true"
        >创建员工</el-button
      >
    </div>
    <el-table :data="users" v-loading="loading">
      <el-table-column prop="employee_id" label="员工 ID" /><el-table-column
        prop="username"
        label="用户名"
      /><el-table-column prop="role" label="角色" /><el-table-column
        label="状态"
        ><template #default="{ row }"
          ><el-tag :type="row.is_active ? 'success' : 'info'">{{
            row.is_active ? "启用" : "禁用"
          }}</el-tag></template
        ></el-table-column
      >
      <el-table-column label="操作"
        ><template #default="{ row }"
          ><el-button link type="primary" @click="resetPassword(row)"
            >重置密码</el-button
          ><el-button
            link
            :type="row.is_active ? 'danger' : 'success'"
            @click="toggleUser(row)"
            >{{ row.is_active ? "禁用" : "启用" }}</el-button
          ></template
        ></el-table-column
      >
    </el-table>
    <el-dialog v-model="dialogVisible" title="创建员工" width="460px">
      <el-form label-width="90px"
        ><el-form-item label="员工 ID"
          ><el-input v-model="form.employee_id" /></el-form-item
        ><el-form-item label="用户名"
          ><el-input v-model="form.username" /></el-form-item
        ><el-form-item label="初始密码"
          ><el-input
            v-model="form.password"
            type="password"
            show-password /></el-form-item
        ><el-form-item label="角色"
          ><el-select v-model="form.role"
            ><el-option label="员工" value="employee" /><el-option
              label="管理员"
              value="admin" /></el-select></el-form-item
      ></el-form>
      <template #footer
        ><el-button @click="dialogVisible = false">取消</el-button
        ><el-button type="primary" @click="createUser"
          >创建</el-button
        ></template
      >
    </el-dialog>
  </section>
</template>

<style scoped>
.users-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
