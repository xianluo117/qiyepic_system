<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import { apiClient, getApiError } from "@/services/api";
import { useAuth } from "@/stores/auth";
import type { User, UserRole } from "@/types";

const auth = useAuth();
const users = ref<User[]>([]);
const loading = ref(false);
const dialogVisible = ref(false);
const form = reactive<{
  employee_id: string;
  username: string;
  password: string;
  role: UserRole;
  supervisor_id: number | null;
}>({
  employee_id: "",
  username: "",
  password: "",
  role: "employee",
  supervisor_id: null,
});

const isSupervisorPage = computed(() => auth.isSupervisor.value);
const supervisors = computed(() =>
  users.value.filter((user) => user.role === "supervisor"),
);

function roleText(role: UserRole): string {
  return role === "admin" ? "管理员" : role === "supervisor" ? "主管" : "员工";
}

function supervisorName(supervisorId: number | null): string {
  if (!supervisorId) return "未分组";
  return (
    supervisors.value.find((user) => user.id === supervisorId)?.username ??
    "未知主管"
  );
}

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

function openCreateDialog(): void {
  Object.assign(form, {
    employee_id: "",
    username: "",
    password: "",
    role: "employee",
    supervisor_id: null,
  });
  dialogVisible.value = true;
}

async function createUser(): Promise<void> {
  try {
    await apiClient.post("/users", form);
    ElMessage.success(isSupervisorPage.value ? "组员创建成功" : "账号创建成功");
    dialogVisible.value = false;
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

async function changeSupervisor(
  user: User,
  supervisorId: number | null,
): Promise<void> {
  try {
    await apiClient.patch(`/users/${user.id}`, { supervisor_id: supervisorId });
    ElMessage.success("主管归属已更新");
    await loadUsers();
  } catch (error) {
    ElMessage.error(getApiError(error));
  }
}

onMounted(loadUsers);
</script>

<template>
  <section class="page-card">
    <div class="users-header">
      <div>
        <h1 class="page-title">
          {{ isSupervisorPage ? "组员管理" : "账号管理" }}
        </h1>
        <p class="page-description">
          {{
            isSupervisorPage
              ? "创建并管理直属员工账号"
              : "管理管理员、主管及员工归属"
          }}
        </p>
      </div>
      <el-button type="primary" @click="openCreateDialog">
        {{ isSupervisorPage ? "创建组员" : "创建账号" }}
      </el-button>
    </div>

    <el-table :data="users" v-loading="loading">
      <el-table-column prop="employee_id" label="员工 ID" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column label="角色">
        <template #default="{ row }">{{ roleText(row.role) }}</template>
      </el-table-column>
      <el-table-column
        v-if="!isSupervisorPage"
        label="直属主管"
        min-width="180"
      >
        <template #default="{ row }">
          <el-select
            v-if="row.role === 'employee'"
            :model-value="row.supervisor_id"
            clearable
            placeholder="未分组"
            @change="changeSupervisor(row, $event ?? null)"
          >
            <el-option
              v-for="supervisor in supervisors"
              :key="supervisor.id"
              :label="`${supervisor.username}（${supervisor.employee_id}）`"
              :value="supervisor.id"
            />
          </el-select>
          <span v-else>{{ supervisorName(row.supervisor_id) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">
            {{ row.is_active ? "启用" : "禁用" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="170">
        <template #default="{ row }">
          <el-button link type="primary" @click="resetPassword(row)">
            重置密码
          </el-button>
          <el-button
            link
            :type="row.is_active ? 'danger' : 'success'"
            @click="toggleUser(row)"
          >
            {{ row.is_active ? "禁用" : "启用" }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="isSupervisorPage ? '创建组员' : '创建账号'"
      width="460px"
    >
      <el-form label-width="90px">
        <el-form-item label="员工 ID">
          <el-input v-model="form.employee_id" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="初始密码">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item v-if="!isSupervisorPage" label="角色">
          <el-select v-model="form.role" @change="form.supervisor_id = null">
            <el-option label="员工" value="employee" />
            <el-option label="主管" value="supervisor" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item
          v-if="!isSupervisorPage && form.role === 'employee'"
          label="直属主管"
        >
          <el-select
            v-model="form.supervisor_id"
            clearable
            placeholder="未分组"
          >
            <el-option
              v-for="supervisor in supervisors"
              :key="supervisor.id"
              :label="`${supervisor.username}（${supervisor.employee_id}）`"
              :value="supervisor.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createUser">创建</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.users-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
}

.users-header .page-description {
  margin-bottom: 0;
}
</style>
