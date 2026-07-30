import { createRouter, createWebHistory } from "vue-router";

import AppLayout from "@/layouts/AppLayout.vue";
import { useAuth } from "@/stores/auth";
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
      component: AppLayout,
      meta: { requiresAuth: true },
      children: [
        { path: "", redirect: "/gallery" },
        { path: "gallery", name: "gallery", component: GalleryView },
        { path: "upload", name: "upload", component: UploadView },
        {
          path: "users",
          name: "users",
          component: UsersView,
          meta: { adminOnly: true },
        },
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
  if (to.path === "/login" && auth.isLoggedIn.value) return "/gallery";
  return true;
});

export default router;
