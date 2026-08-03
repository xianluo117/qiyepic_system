import { createRouter, createWebHistory } from "vue-router";

import AdminLayout from "@/layouts/AdminLayout.vue";
import EmployeeLayout from "@/layouts/EmployeeLayout.vue";
import { useAuth } from "@/stores/auth";
import AdminLogsView from "@/views/AdminLogsView.vue";
import GalleryView from "@/views/GalleryView.vue";
import LoginView from "@/views/LoginView.vue";
import UploadView from "@/views/UploadView.vue";
import UsersView from "@/views/UsersView.vue";

const employeeRoutes = [
  {
    path: "/gallery",
    name: "gallery",
    component: EmployeeLayout,
    meta: { requiresAuth: true, employeeOnly: true },
    children: [{ path: "", component: GalleryView }],
  },
  {
    path: "/upload",
    name: "upload",
    component: EmployeeLayout,
    meta: { requiresAuth: true, employeeOnly: true },
    children: [{ path: "", component: UploadView }],
  },
  {
    path: "/team",
    name: "team-users",
    component: EmployeeLayout,
    meta: { requiresAuth: true, supervisorOnly: true },
    children: [{ path: "", component: UsersView }],
  },
];

const adminRoutes = [
  {
    path: "/admin/images",
    name: "admin-images",
    component: AdminLayout,
    meta: { requiresAuth: true, adminOnly: true },
    children: [{ path: "", component: GalleryView }],
  },
  {
    path: "/admin/users",
    name: "admin-users",
    component: AdminLayout,
    meta: { requiresAuth: true, adminOnly: true },
    children: [{ path: "", component: UsersView }],
  },
  {
    path: "/admin/logs",
    name: "admin-logs",
    component: AdminLayout,
    meta: { requiresAuth: true, adminOnly: true },
    children: [{ path: "", component: AdminLogsView }],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "employee-login",
      component: LoginView,
      props: { portal: "employee" },
    },
    {
      path: "/admin",
      name: "admin-login",
      component: LoginView,
      props: { portal: "admin" },
    },
    { path: "/login", redirect: "/" },
    ...employeeRoutes,
    ...adminRoutes,
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuth();
  const isAdminPortal = to.path.startsWith("/admin");
  const loginPath = isAdminPortal ? "/admin" : "/";

  if (to.meta.requiresAuth && !auth.isLoggedIn.value) return loginPath;
  if (auth.isLoggedIn.value && !auth.user.value) {
    try {
      await auth.loadCurrentUser();
    } catch {
      auth.logout();
      return loginPath;
    }
  }
  if (to.meta.adminOnly && !auth.isAdmin.value) return "/gallery";
  if (to.meta.employeeOnly && auth.isAdmin.value) return "/admin/images";
  if (to.meta.supervisorOnly && !auth.isSupervisor.value) return "/gallery";
  if (to.name === "admin-login" && auth.isLoggedIn.value) {
    return auth.isAdmin.value ? "/admin/images" : "/gallery";
  }
  if (to.name === "employee-login" && auth.isLoggedIn.value) {
    return auth.isAdmin.value ? "/admin/images" : "/gallery";
  }
  return true;
});

export default router;
