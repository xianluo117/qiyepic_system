import { createRouter, createWebHistory } from "vue-router";

import AdminLayout from "@/layouts/AdminLayout.vue";
import EmployeeLayout from "@/layouts/EmployeeLayout.vue";
import { useAuth } from "@/stores/auth";
import AdminLogsView from "@/views/AdminLogsView.vue";
import GalleryView from "@/views/GalleryView.vue";
import LoginView from "@/views/LoginView.vue";
import UploadView from "@/views/UploadView.vue";
import UsersView from "@/views/UsersView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView },
    {
      path: "/",
      component: EmployeeLayout,
      meta: { requiresAuth: true, employeeOnly: true },
      children: [
        { path: "", redirect: "/gallery" },
        { path: "gallery", name: "gallery", component: GalleryView },
        { path: "upload", name: "upload", component: UploadView },
      ],
    },
    {
      path: "/admin",
      component: AdminLayout,
      meta: { requiresAuth: true, adminOnly: true },
      children: [
        { path: "", redirect: "/admin/images" },
        { path: "images", name: "admin-images", component: GalleryView },
        { path: "users", name: "admin-users", component: UsersView },
        { path: "logs", name: "admin-logs", component: AdminLogsView },
      ],
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuth();
  if (to.meta.requiresAuth && !auth.isLoggedIn.value) return "/login";
  if (auth.isLoggedIn.value && !auth.user.value) {
    try {
      await auth.loadCurrentUser();
    } catch {
      auth.logout();
      return "/login";
    }
  }
  if (to.meta.adminOnly && !auth.isAdmin.value) return "/gallery";
  if (to.meta.employeeOnly && auth.isAdmin.value) return "/admin/images";
  if (to.path === "/login" && auth.isLoggedIn.value) {
    return auth.isAdmin.value ? "/admin/images" : "/gallery";
  }
  return true;
});

export default router;
