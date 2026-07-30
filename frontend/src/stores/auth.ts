import { computed, ref } from "vue";

import { apiClient } from "@/services/api";
import type { User } from "@/types";

const token = ref(localStorage.getItem("access_token") ?? "");
const user = ref<User | null>(null);

export function useAuth() {
  const isLoggedIn = computed(() => Boolean(token.value));
  const isAdmin = computed(() => user.value?.role === "admin");

  async function login(username: string, password: string): Promise<void> {
    const form = new URLSearchParams({ username, password });
    const { data } = await apiClient.post<{ access_token: string }>(
      "/auth/login",
      form,
      { headers: { "Content-Type": "application/x-www-form-urlencoded" } },
    );
    token.value = data.access_token;
    localStorage.setItem("access_token", data.access_token);
    await loadCurrentUser();
  }

  async function loadCurrentUser(): Promise<User | null> {
    if (!token.value) {
      user.value = null;
      return null;
    }
    const { data } = await apiClient.get<User>("/auth/me");
    user.value = data;
    return data;
  }

  function logout(): void {
    token.value = "";
    user.value = null;
    localStorage.removeItem("access_token");
  }

  return { token, user, isLoggedIn, isAdmin, login, loadCurrentUser, logout };
}
